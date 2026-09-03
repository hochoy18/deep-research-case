# HITL（Human-in-the-Loop）Plan Confirmation 交互说明

本文档以一次完整的人 ↔ 前端 ↔ LangGraph 后端交互为例，描述
**人输入、前端、后端 graph 三方**在每一轮提交 / 响应中各自做了什么。

示例场景：用户研究「企业级 AI Agent 落地方案」。

---

## 0. 状态机一览

后端 graph（见 `backend/src/agent/graph.py`）的节点与路由：

```
START
  └─► generate_plan                # ① 必入口：先产出研究计划
        ├─► evaluate_plan  ─► awaiting_plan_confirmation   # ② 停在"等待确认"
        ├─► evaluate_plan  ─► replan ─► generate_plan      # ③ 用户改了 → 重新规划
        └─► evaluate_plan  ─► generate_query              # ④ 用户认可 → 走研究主流程
                                  ├─► web_search   (并行 Send)
                                  └─► critique
                                        ├─► web_search   (循环)
                                        └─► final_answer ─► END
```

| 节点 | 行为 |
|---|---|
| `generate_plan` | 用 LLM 把"原始问题 + 用户补充的细节"包装成一份 markdown 研究计划 |
| `awaiting_plan_confirmation` | `lambda state, config: state` —— **不修改 state**，让图停在这里 |
| `replan` | 把 `plan_status` 重置为 `"unconfirmed"`，回到 `generate_plan` 重做 |
| `generate_query` | 基于 messages + plan 生成 N 个搜索查询 |
| `web_search` | 单条查询的网络检索 + 摘要 |
| `critique` | 反思搜索结果，判断是否足够 / 需要 follow-up |
| `final_answer` | 综合所有结果写最终报告 |

---

## 1. 第一次页面输入：提出问题

**人在前端输入框里敲入**：

> 现在企业级的 AI Agent 落地方案深度调研

并在底栏选 Effort（低/中/高）和 Model（qwen-turbo / qwen-plus / ...），点 **「探索」** 按钮。

### 1.1 前端做了什么

`InputForm.handleInternalSubmit` → `App.handleSubmit`：

```ts
// frontend/src/components/InputForm.tsx
onSubmit(internalInputValue, effort, model);   // 把 ① 输入文字、② effort、③ model 一起给 App
```

`App.handleSubmit` 紧接着做几件事：

1. **快照 effort / model**（如果是首条消息）
   ```ts
   if (thread.messages.length === 0) {
     setSavedEffort(effort);
     setSavedModel(model);
   }
   ```
2. **把 effort 翻译成具体的搜索预算**
   ```ts
   switch (currentEffort) {
     case "low":    initial_search_query_count = 1; max_research_loops = 1;
     case "medium": initial_search_query_count = 3; max_research_loops = 3;
     case "high":   initial_search_query_count = 5; max_research_loops = 10;
   }
   ```
3. **拼装要发给后端的 state**，调用 `thread.submit(...)`：
   ```ts
   thread.submit({
     messages: [{ type: "human", content: "现在企业级的 AI Agent 落地方案深度调研", id: ... }, ...],
     initial_search_query_count: 3,
     max_research_loops: 3,
     reasoning_model: "qwen-plus-latest",
     plan_status: "unconfirmed",          // ← 关键：标记"还没有确认的计划"
   });
   ```
   实际把消息以 SSE 流式发给 `http://localhost:2024`（dev）或 `:8123`（prod）的 `assistantId: "agent"`。

### 1.2 后端 LangGraph 做了什么

LangGraph SDK 根据 `messagesKey: "messages"` 把 `messages` 注入 `OverallState`，
graph 从 `START` 立即进入 `generate_plan` 节点：

```python
# backend/src/agent/graph.py
def generate_plan(state, config):
    if state.get("plan_status", "unconfirmed") != "unconfirmed":
        return {}                              # 不是第一次 → 跳过
    agent = Agent(model_id=...)
    agent.set_step_prompt(plan_instructions)
    response = agent.step(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),  # "现在企业级..."
        research_proposal=state.get("plan", ""),
    )
    response = Post.extract_pattern(response, pattern="markdown")
    return {
        "messages": [AIMessage(content=response)],   # 把计划作为 AI 消息回写
        "plan": response,                            # 计划原文留底
        "plan_status": "unconfirmed",                # 状态：未确认
        "plan_messages": [AIMessage(content=response)],
    }
```

接着 `evaluate_plan(state, config)` 根据 `plan_status` 做路由判断：

```python
if state.get("plan_status", "unconfirmed") == "unconfirmed":
    return "awaiting_plan_confirmation"   # ← 本例走这里
```

`awaiting_plan_confirmation` 节点是 `lambda state, config: state`，
**不修改 state、不返回 Send 也不路由**，让 LangGraph 暂停在原地等待用户下一次输入。

### 1.3 后端 → 前端 流式推送

LangGraph 在每个节点返回值更新 state 时会通过 SSE 向客户端广播事件，
前端 `useStream` 的 `onUpdateEvent` 收到：

| 事件 | 来源节点 | 前端处理 |
|---|---|---|
| `event.generate_plan` | `generate_plan` | `setAwaitingPlanConfirmation("confirmed")`；追加 ProcessedEvent `{title: "生成计划", data: plan}` |

`ChatMessagesView` 检测到 `activityForThisBubble` 里存在 `title === "生成计划"`，
进入"研究计划"分支：

- 把 AI 消息以 `<ReactMarkdown>` 渲染（不显示 ActivityTimeline）
- 在消息底部渲染一个 **「initiate research」** 按钮（绑定 `onStartResearch`）

---

## 2. 第二次页面输入：补充细节

此时人看到**已经生成的研究计划 markdown** + 蓝色 **「initiate research」** 按钮。

**用户在 InputForm 输入框里敲入详细配置**（自然语言 / 半结构化都行）：

````text
特定行业深度：科技，电商，零售
分析维度 ：技术架构与选型，应用场景与案例，成本效益分析
地理市场范围：欧美为主，国内次之，
目标受众：
- **A. 技术决策者**（CTO、IT 负责人）- 侧重技术架构与选型
- **B. 业务决策者**（CEO、业务负责人）- 侧重价值与 ROI

报告详细程度：50页左右
````

然后点 **「探索」**（或者点 AI 消息下的「initiate research」按钮）。

> 注：当前 `InputForm` 还没有 `forwardRef` / `useImperativeHandle`，
> 所以「initiate research」按钮目前**不会自动填表**；
> 实际可行的两条路径是：① 在 InputForm 里手动输入 `需求确认` 提交；
> ② 在 InputForm 里输入上面这段详细配置后点探索。
> 两种路径的语义差异见 §2.3。

### 2.1 前端做了什么

`InputForm.handleInternalSubmit` 再次调用 `App.handleSubmit`。
关键差异：

- `thread.messages.length` 已经不为 0 → **不再覆盖** `savedEffort` / `savedModel`
- `awaitingPlanConfirmation` 是 `"confirmed"`（第一次收到 `generate_plan` 事件时被设置）
- 拼装的 state：

```ts
thread.submit({
  messages: [...prev, { type: "human", content: "<上面那段 text>", id: ... }],
  initial_search_query_count: 3,
  max_research_loops: 3,
  reasoning_model: "qwen-plus-latest",
  plan_status: "confirmed",          // ← 关键：表示"已经有计划了，别再生成"
});
```

### 2.2 后端 LangGraph 做了什么

再次进入 `START → generate_plan`：

```python
if state.get("plan_status", "unconfirmed") != "unconfirmed":
    return {}                          # ← 本例走这里：plan_status="confirmed"，不重新生成
```

然后 `evaluate_plan`：

```python
if state.get("plan_status", "unconfirmed") == "unconfirmed":   # False，跳过
    return "awaiting_plan_confirmation"

if not plan:                                                    # 已有 plan，跳过
    return "replan"

context = get_last_user_response(state["messages"])            # 取出第二次输入的那段 text

# 短路：用户用了「开始研究 / 需求确认」字样 → 直接进研究
if "开始研究" in context:   return GENERATE_SEARCH_NODE
if "需求确认" in context:   return GENERATE_SEARCH_NODE

# 否则用 LLM 判断当前 plan 是否能满足用户最新的细化诉求
agent = JsonAgent(..., keys=PlanReflection)
agent.set_step_prompt(plan_reflection_instructions)
result = agent.step(research_proposal=state.get("plan", ""), context=context)
if result.satisfy:
    return GENERATE_SEARCH_NODE        # LLM 认为现有 plan 够用 → 走研究
return "replan"                        # LLM 认为 plan 还不够 → 回到 generate_plan 重做
```

**两条语义不同的路径**：

| 用户在 InputForm 输入 | 关键字 | evaluate_plan 走法 | 含义 |
|---|---|---|---|
| `需求确认` 或 `开始研究` | 命中快捷词 | 直接进 `generate_query` | "我同意你的计划，开始执行" |
| 详细配置（行业/维度/受众/页数 等） | 不命中 | LLM 判断 `result.satisfy` | "请按这些细节调整；满意就去做，不满意就重做计划" |

如果走 `replan`：

```python
def replan(state, config):
    return {"plan_status": "unconfirmed"}    # 重置状态
```

→ `replan` 节点连到 `generate_plan` → **重新生成计划**（基于完整 messages）→ 再次停在
`awaiting_plan_confirmation`，UI 再次出现新计划 + 「initiate research」按钮。

### 2.3 后端 → 前端 流式推送

- 如果 LLM 判断 `satisfy`：
  - 用户**不会**再看到新的 "生成计划" 事件；
  - 紧接着会看到 `generate_query` 事件：`{title: "生成搜索查询", data: "query1, query2, ..."}`，
    然后每个 `web_search` 一个事件，`critique` 一个事件，
    最后 `finalize_answer` 一个事件 + AI 消息正文。
- 如果 LLM 判断不满足：
  - 用户会看到第二条 "生成计划" 事件（带新内容），ActivityTimeline 标题变成"initiate research"，
    再次出现「initiate research」按钮。

---

## 3. 完整事件流（时序图）

```
人              前端(App/InputForm)            后端 graph                LLM
│                       │                          │                      │
│ ① 敲入「现在企业级...」 │                          │                      │
│  选 effort/model  │                          │                      │
│  点「探索」        │                          │                      │
│ ─────────────────► │                          │                      │
│                       │ submit({messages,plan_status:"unconfirmed"})  │
│                       │ ──────────────────────────────────────────►  │
│                       │                          │ generate_plan()    │
│                       │                          │ ─── plan LLM ──────►│
│                       │                          │ ◄──── plan md ──────│
│                       │                          │ await confirm       │
│                       │ ◄── event.generate_plan ──│                    │
│ 渲染计划 + 按钮 ◄──── │                          │                      │
│                       │                          │                      │
│ ② 敲入「行业/维度...」 │                          │                      │
│  点「探索」        │                          │                      │
│ ─────────────────► │                          │                      │
│                       │ submit({messages,plan_status:"confirmed"})    │
│                       │ ──────────────────────────────────────────►  │
│                       │                          │ generate_plan()→{} │
│                       │                          │ evaluate_plan()    │
│                       │                          │  ├ 命中快捷词 ─────►│
│                       │                          │  │ 或 plan_reflect │
│                       │                          │  │   LLM 判断 ─────►│
│                       │                          │  ◄── satisfy / no ──│
│                       │                          │  ├ 满足→generate_query
│                       │                          │  │   →web_search×N
│                       │                          │  │   →critique
│                       │                          │  │   →可能再 web_search
│                       │                          │  │   →final_answer
│                       │                          │  └ 不满足→replan→generate_plan
│                       │ ◄── event.generate_query ──│ (依次)             │
│                       │ ◄── event.web_research ───│                    │
│                       │ ◄── event.reflection ─────│                    │
│                       │ ◄── event.finalize_answer ─│                    │
│                       │ ◄── messages (AI 正文) ──│                    │
│ 渲染完整报告 ◄──── │                          │                      │
```

---

## 4. 关键状态字段（OverallState 中被这次交互用到的）

| 字段 | 来源 | 用途 |
|---|---|---|
| `messages` | 前端每次 submit 追加一条 human | 真实的人机对话历史，所有 prompt 都会从这里取上下文 |
| `plan` | `generate_plan` 节点写入 | 持久化的研究计划，后续 `generate_query` / `web_search` / `final_answer` 都会作为 `research_proposal` 注入 |
| `plan_status` | `"unconfirmed"` / `"confirmed"` | 决定 `generate_plan` 是否真的要重做；也是 evaluate_plan 的路由开关 |
| `plan_messages` | `generate_plan` 节点写入 | 仅供 `get_research_topic` 在重做计划时拼上下文 |
| `initial_search_query_count` | 前端从 effort 翻译 | `generate_query` 一次产出多少条搜索词 |
| `max_research_loops` | 前端从 effort 翻译 | `route_evaluate` 决定 critique 还能递归几轮 |
| `reasoning_model` | 前端从模型选择传入 | `critique` 节点用它做反思 |
| `web_search_result` | `web_search` 节点累计 | critique / final_answer 拼 summaries 的来源 |
| `sources_gathered` | `web_search` 节点累计 | final_answer 替换 short_url 用的来源表 |
| `is_sufficient` / `follow_up_queries` | `critique` 节点写入 | route_evaluate 决定继续 web_search 还是 final_answer |

---

## 5. 给开发者的速查表

- 想**强制重新生成计划**：在 `evaluate_plan` 把 `plan_status` 重置为 `"unconfirmed"`
  （即发请求时把 `plan_status: "unconfirmed"` 一并发过去）。
- 想**跳过计划阶段直接进入研究**：把 `plan` 字段填好 + 消息里包含 `需求确认` 或 `开始研究`。
- 想**让 `web_search` 更深入**：前端把 `effort` 切到 high（5 query / 10 loop），
  或后端在 `Configuration` 里调大默认值。
- 想**观测节点耗时**：所有节点都用 `logger.info(...)` 打了状态与响应，
  在 `backend/src/agent/logs/` 下查 loguru 输出。
- 想**在 UI 里手工触发"initiate research"**：
  当前 `InputForm` 还没 `forwardRef`，要么补 `useImperativeHandle({ setInputValue, submitInput })`，
  要么直接在 InputForm 里输入 `需求确认` 提交。
