可以。这个问题其实是 **LangGraph 做生产级 Agent 时非常关键的一层**。

很多 Demo 里的 Human-in-the-loop（HITL）只是：

```text
Agent
 ↓
“需要确认”
 ↓
用户点一下
 ↓
继续
```

但生产级的 HITL 不是简单地“加一个人工审批节点”，而是要解决：

> **什么时候必须让人介入、让人看什么、允许人修改什么、暂停后如何恢复、人工拒绝后 Agent 怎么继续，以及什么情况下根本不应该让 Agent 自己决定。**

下面从 Plan-and-Execute 的完整生命周期来讲。

---

# 一、先给结论：HITL 到底应该放在哪里？

一个生产级 Plan-and-Execute 大致是：

```text
                         User Goal
                            │
                            ▼
                        ┌────────┐
                        │ Planner│
                        └───┬────┘
                            │
                            ▼
                     Plan Validation
                            │
                            ▼
                       Scheduler
                            │
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
              Task A      Task B     Task C
                 │          │          │
                 └──────────┼──────────┘
                            ▼
                         Evaluate
                            │
                    ┌───────┴────────┐
                    │                │
                    ▼                ▼
                 Continue          Re-plan
                    │                │
                    └───────┬────────┘
                            ▼
                         Finalize
                            │
                            ▼
                          Human
                            │
                       Approve / Edit
                            │
                            ▼
                         Execute
```

但实际上，**HITL 可以出现在至少 6 个位置**：

| 环节         | 是否常见  | 典型用途       |
| ---------- | ----- | ---------- |
| 用户目标确认     | ⭐⭐⭐   | 需求有歧义      |
| Plan 审批    | ⭐⭐⭐⭐  | 高风险/高成本计划  |
| Task 执行前审批 | ⭐⭐⭐⭐⭐ | 写邮件、下单、改数据 |
| Tool 调用审批  | ⭐⭐⭐⭐⭐ | 敏感 API     |
| 结果审核       | ⭐⭐⭐⭐  | 高风险输出      |
| 最终结果确认     | ⭐⭐⭐   | 对外发布/提交    |

真正生产级的关键是：

> **不是每一步都让人审批，而是根据风险决定“Human Boundary”。**

---

# 二、为什么需要 HITL？

先看一个没有 HITL 的 Agent。

用户说：

> “帮我给这个客户处理退款。”

Agent：

```text
Planner
 ↓
查订单
 ↓
确认退款资格
 ↓
调用退款 API
 ↓
退款 $5,000
 ↓
给客户发邮件
```

整个过程：

```text
LLM → Tool → Tool → Tool → Tool
```

问题是：

**LLM 最终获得了“现实世界的执行权”。**

它不仅是在生成文本，而是在：

* 修改数据库
* 转钱
* 发邮件
* 创建订单
* 删除数据
* 修改权限
* 发布内容

这时候：

> Agent 的错误不再只是“回答错了”。

而可能变成：

> **真实世界的副作用。**

所以 HITL 本质上是：

> **在 Agent 的推理能力和现实世界副作用之间增加一个人工控制边界。**

---

# 三、最重要的原则：不是“Agent 做不到”，而是“Agent 不应该自己做”

这是理解 HITL 最关键的一点。

例如：

### 低风险

```text
搜索网页
读取文档
总结信息
```

没必要人工。

### 中风险

```text
修改 CRM
创建工单
生成内部报告
```

可以根据业务规则决定。

### 高风险

```text
退款
付款
删除数据
发送正式邮件
修改权限
发布公告
```

通常需要人工。

所以生产系统应该有一个：

```text
Risk Classification
```

例如：

```python
def classify_risk(task):

    if task.tool in [
        "refund",
        "payment",
        "delete_database",
        "change_permission"
    ]:
        return "HIGH"

    if task.tool in [
        "update_crm",
        "create_ticket"
    ]:
        return "MEDIUM"

    return "LOW"
```

然后：

```text
LOW
 ↓
Agent 自动执行

MEDIUM
 ↓
根据 policy 决定

HIGH
 ↓
Human Approval
```

---

# 四、第一种 HITL：Plan Approval

这是最容易理解的一种。

用户说：

> “帮我制定一个竞品调研方案。”

Planner 生成：

```text
Plan v1

Task 1:
调研 OpenAI

Task 2:
调研 Anthropic

Task 3:
调研 Google

Task 4:
比较产品能力

Task 5:
生成报告
```

这时候可以：

```text
Planner
   ↓
Plan
   ↓
Human Approval
   ↓
Scheduler
```

人工看到：

```text
你的 Agent 准备执行：

1. 搜索三家公司公开资料
2. 分析产品能力
3. 对比价格
4. 生成报告

预计：
- 15 次搜索
- 约 20 分钟
- 预计成本 $X

[批准] [修改计划] [取消]
```

---

## 这种模式什么时候特别有价值？

比如：

### 高成本任务

```text
预计调用 200 次 API
```

### 长任务

```text
预计执行 2 小时
```

### 目标可能理解错

```text
用户说：
“帮我分析这个项目。”
```

Agent 认为：

```text
我要分析技术、市场、财务、法律
```

用户其实只想：

```text
分析技术架构
```

如果直接执行，浪费大量资源。

所以：

```text
User
 ↓
Planner
 ↓
Human
 ↓
Executor
```

可以避免方向性错误。

---

# 五、第二种 HITL：Task Execution Approval

这是生产环境最常见的一种。

例如：

```text
Task 1：搜索客户信息
Task 2：分析订单
Task 3：生成退款方案
Task 4：执行退款
Task 5：发送邮件
```

前 3 个可以自动。

到 Task 4：

```text
Task 4
退款 $5,000
      ↓
Human Approval
```

人确认：

```text
退款金额：$5,000
客户：xxx
订单：xxx
原因：xxx

[Approve]
[Reject]
```

然后：

```text
Approve
 ↓
Executor
 ↓
refund_api()
```

这是一种非常推荐的设计。

---

# 六、为什么不要让人工审批整个 Agent？

一个很常见的错误：

```text
Task A
 ↓
Human
 ↓
Task B
 ↓
Human
 ↓
Task C
 ↓
Human
 ↓
Task D
```

这实际上已经不是 Agent 了。

用户会变成：

> “你每一步都问我，那我自己做不就好了？”

所以生产系统追求：

> **Human only at meaningful decision boundaries.**

比如：

```text
搜索
自动

分析
自动

生成方案
自动

执行高风险动作
人工

后续低风险任务
自动
```

这叫：

> **Selective Human-in-the-loop**

---

# 七、第三种：Tool Approval

这个比 Task Approval 更细。

例如 Agent 有：

```text
Tools:

search_web
read_database
update_database
send_email
refund
delete_user
```

你可以给 Tool 定义风险：

```python
TOOLS = {

    "search_web": {
        "risk": "LOW"
    },

    "read_database": {
        "risk": "LOW"
    },

    "update_database": {
        "risk": "MEDIUM"
    },

    "send_email": {
        "risk": "HIGH"
    },

    "refund": {
        "risk": "HIGH"
    }
}
```

Executor：

```python
def execute_tool(tool_call, state):

    risk = get_risk(tool_call.tool)

    if risk == "HIGH":

        interrupt({
            "type": "tool_approval",
            "tool": tool_call.tool,
            "arguments": tool_call.arguments
        })

    return tool.execute(
        tool_call.arguments
    )
```

于是 Agent 可以自动推理：

```text
我要退款
```

但不能自动：

```text
refund(...)
```

必须：

```text
LLM Decision
    ↓
Policy
    ↓
Human
    ↓
Tool
```

这个架构比简单的：

```text
Task → Human
```

更灵活。

---

# 八、Task Approval 和 Tool Approval 的区别

这个区别很重要。

假设：

```text
Task：

“处理客户退款”
```

Task 里面可能有：

```text
1. 查订单
2. 查退款政策
3. 计算退款金额
4. 调用退款 API
5. 发邮件
```

如果你做：

### Task-level HITL

```text
处理退款
 ↓
Human
 ↓
整个 Task 执行
```

优点：

> 简单。

缺点：

> 人工看到的粒度比较粗。

---

### Tool-level HITL

```text
查订单
 ↓
自动

查政策
 ↓
自动

计算金额
 ↓
自动

refund()
 ↓
Human
 ↓
执行

send_email()
 ↓
Human / 自动
```

优点：

> 非常精细。

生产系统通常会组合使用：

```text
Plan-level
+
Task-level
+
Tool-level
```

而不是只选一个。

---

# 九、第四种：结果审核

还有一种很重要：

> Agent 可以执行，但结果不能直接使用。

比如：

```text
Agent
 ↓
生成法律合同草稿
 ↓
Human Review
 ↓
修改
 ↓
Final
```

或者：

```text
Agent
 ↓
生成对外公告
 ↓
Human
 ↓
发布
```

这时候 Human 不一定是在批准“执行”。

而是在批准：

> **Agent 产生的 Artifact。**

例如：

```python
artifact = {
    "type": "email",
    "content": "...",
    "recipient": "...",
}
```

Human 可以：

```text
Approve
Edit
Reject
```

这比简单的 Boolean：

```python
approved = True
```

更生产化。

---

# 十、第五种：用户修改 Agent 的 Plan

这是 HITL 非常强的一种模式。

Agent：

```text
Plan v1

1. 调研 OpenAI
2. 调研 Anthropic
3. 调研 Google
4. 做对比
```

用户：

> “不用调研 Google，换成 Microsoft。”

这不是：

```text
Reject
```

而是：

```text
Human Feedback
 ↓
Planner
 ↓
Plan v2
```

即：

```text
Plan v1
 ↓
Human
 ↓
Feedback
 ↓
Re-plan
 ↓
Plan v2
 ↓
Execute
```

这才真正体现了：

> **Human 和 Agent 共同规划。**

---

# 十一、LangGraph 为什么特别适合 HITL？

因为 LangGraph 的核心抽象本身就是：

```text
State
+
Node
+
Edge
```

所以 HITL 可以自然地变成：

```text
Node
 ↓
Interrupt
 ↓
Persist State
 ↓
Human
 ↓
Resume
 ↓
Node
```

也就是说：

> **Agent 不需要一直占着一个进程等人。**

这是生产系统非常重要的。

例如：

```text
10:00

Agent:
准备退款 $5,000

       ↓

interrupt()

       ↓

State 保存

       ↓

Agent Run 结束 / 暂停


14:30

Human:
Approve

       ↓

Resume

       ↓

Agent 从暂停位置继续
```

这就是 HITL 和普通：

```python
input("Approve?")
```

的巨大区别。

---

# 十二、生产级 HITL 最核心的其实是 Interrupt

概念代码：

```python
def approval_node(state):

    action = state.pending_action

    decision = interrupt({
        "type": "approval",
        "action": action,
        "reason": action.reason,
        "risk": action.risk,
        "arguments": action.arguments
    })

    return {
        "human_decision": decision
    }
```

Agent 到这里：

```text
Executor
 ↓
Approval Node
 ↓
interrupt()
```

Graph 暂停。

之后：

```text
Human
 ↓
Approve / Reject / Edit
 ↓
resume()
```

Graph：

```text
Approval Node
 ↓
继续
```

关键不是 `interrupt()` 本身。

而是：

> **Interrupt 前后的 State 必须是可持久化、可恢复、可追踪的。**

---

# 十三、为什么必须有 Checkpoint？

没有 checkpoint：

```text
Agent
 ↓
interrupt
 ↓
进程挂了
 ↓
什么都没了
```

有 checkpoint：

```text
Agent
 ↓
Task 1 ✓
Task 2 ✓
Task 3 pending approval
 ↓
Checkpoint
 ↓
等待
 ↓
Human approve
 ↓
Resume
 ↓
Task 3
```

所以：

```text
HITL
+
Checkpoint
```

在生产环境基本是绑定关系。

---

# 十四、这里会出现一个非常重要的问题：暂停多久？

可能：

```text
5 秒
```

也可能：

```text
5 天
```

所以 Agent Runtime 必须允许：

```text
Run
 ↓
WAITING_FOR_HUMAN
```

而不是：

```python
while not approved:
    sleep(10)
```

后者是错误的生产架构。

正确的是：

```text
Agent Run
 ↓
Persist State
 ↓
Status = WAITING_FOR_APPROVAL
 ↓
释放 Runtime
```

用户批准以后：

```text
Approval Event
 ↓
Resume Run
 ↓
Continue Graph
```

---

# 十五、HITL 的状态机

生产系统最好明确设计 Agent Status：

```text
PENDING
   ↓
RUNNING
   ↓
WAITING_FOR_APPROVAL
   ↓
RUNNING
   ↓
COMPLETED
```

也可能：

```text
WAITING_FOR_APPROVAL
        ↓
     REJECTED
        ↓
      REPLAN
```

或者：

```text
WAITING_FOR_APPROVAL
        ↓
     EXPIRED
        ↓
      CANCELLED
```

所以 HITL 实际上会把 Agent 从一个简单的：

```text
Running / Done
```

变成：

```text
State Machine
```

---

# 十六、Human 的输入不能只设计成 True / False

Demo 经常：

```python
approved = True
```

生产级通常至少需要：

```python
HumanDecision = {

    "decision": "approve",

    "user_id": "...",

    "timestamp": "...",

    "comment": "...",

    "modified_data": ...
}
```

Decision 可以是：

```text
APPROVE
REJECT
EDIT
RETRY
SKIP
REPLAN
CANCEL
```

例如：

```text
Agent：

准备退款 $5,000

Human：

EDIT

退款金额：
$3,000

备注：
只退未使用部分
```

然后：

```text
Human Edit
 ↓
Validation
 ↓
Executor
```

---

# 十七、这里必须做权限控制

假设：

```text
普通员工
```

不能批准：

```text
>$10,000 refund
```

那么：

```python
if refund_amount > 10000:

    require_role("finance_manager")
```

甚至：

```text
$0 - $1,000
→ Agent 自动

$1,000 - $10,000
→ Team Lead

>$10,000
→ Finance Manager

>$100,000
→ CFO
```

这时候 HITL 已经从：

> “让用户点一下确认”

升级成：

> **Policy-driven Human Approval。**

这才是企业生产环境真正需要的。

---

# 十八、Human 不应该看到整个 State

这个也非常重要。

State 可能有：

```text
100 个 Task
500 个 Tool Result
20 个网页
用户信息
内部系统信息
```

Human 不需要全部看。

应该有一个：

```python
approval_context = build_approval_context(
    state,
    pending_task
)
```

只展示：

```text
┌───────────────────────────┐
│ Approval Required          │
├───────────────────────────┤
│ Action: Refund             │
│ Amount: $5,000             │
│ Customer: John             │
│ Order: #12345              │
│ Reason: Duplicate payment  │
│                            │
│ Evidence:                  │
│ - Order details            │
│ - Refund policy            │
│                            │
│ [Approve] [Edit] [Reject]  │
└───────────────────────────┘
```

原则：

> **Human 应该看到“做决定所需要的信息”，而不是 Agent 的全部上下文。**

---

# 十九、没有 HITL 和有 HITL，到底区别在哪里？

用一个真实例子比较最直观。

## 场景：客服退款 Agent

用户：

> “帮我处理订单 12345 的退款。”

---

### 没有 HITL

```text
User
 ↓
Planner
 ↓
查订单
 ↓
查政策
 ↓
计算退款
 ↓
refund()
 ↓
send_email()
 ↓
Done
```

优点：

* 全自动
* 延迟低
* 用户体验简单
* 人力成本低

缺点：

* Agent 判断错会直接产生副作用
* 权限边界难控制
* 很难处理例外
* 错误成本可能非常高

---

### 有 HITL

```text
User
 ↓
Planner
 ↓
查订单
 ↓
查政策
 ↓
计算退款
 ↓
Risk Check
 ↓
Human Approval
 ↓
refund()
 ↓
send_email()
 ↓
Done
```

优点：

* 高风险动作可控
* 人可以纠正 Agent
* 容错能力强
* 更适合金融、企业、运营场景

缺点：

* 增加 latency
* 增加人工成本
* 用户体验更复杂
* Approval 设计不好会造成大量人工干预

---

# 二十、真正生产级的区别其实是这张表

| 维度    | 无 HITL     | 有 HITL  |
| ----- | ---------- | ------- |
| 自动化程度 | ⭐⭐⭐⭐⭐      | ⭐⭐⭐⭐    |
| 执行速度  | 快          | 较慢      |
| 高风险操作 | 不安全        | 可控      |
| 异常处理  | Agent 自己处理 | 人可介入    |
| 计划纠错  | 自动         | 人可修改    |
| 审计    | 主要看日志      | 有人工决策记录 |
| 运营成本  | 低          | 较高      |
| 系统复杂度 | 低          | 高       |
| 企业场景  | 有限制        | 更适合     |
| 金融/支付 | 谨慎         | 强烈推荐    |
| 内容发布  | 谨慎         | 推荐      |
| 纯信息查询 | 推荐无 HITL   | 通常没必要   |

---

# 二十一、一个更合理的生产架构

我会推荐：

```text
                         User
                          │
                          ▼
                       Planner
                          │
                          ▼
                   Plan Validator
                          │
                          ▼
                     Risk Engine
                          │
              ┌───────────┴───────────┐
              │                       │
           Low Risk                High Risk
              │                       │
              │                    Human
              │                       │
              │                Approve / Edit
              │                       │
              └───────────┬───────────┘
                          ▼
                       Scheduler
                          │
                 ┌────────┼────────┐
                 ▼        ▼        ▼
               Task A   Task B   Task C
                 │        │        │
                 └────────┼────────┘
                          ▼
                       Executor
                          │
                          ▼
                     Tool Policy
                          │
                    ┌─────┴─────┐
                    │           │
                 Safe Tool   Sensitive Tool
                    │           │
                    │         Human
                    │           │
                    └─────┬─────┘
                          ▼
                       Result
                          │
                          ▼
                      Evaluator
                          │
                  ┌───────┴────────┐
                  ▼                ▼
               Success          Failure
                  │                │
                  ▼                ▼
               Finalize         Retry/Replan
                  │
                  ▼
                 END
```

这里我特别建议加入：

# **Risk Engine**

因为：

> **什么时候需要 HITL，不应该由 LLM 自己决定。**

---

# 二十二、为什么不能让 LLM 自己决定“要不要人工审批”？

例如：

```python
if llm.thinks_human_needed():
    interrupt()
```

看起来很 Agentic。

但生产环境很危险。

因为可能出现：

```text
高风险操作
 ↓
LLM 判断：
“我认为风险不高”
 ↓
直接执行
```

这相当于：

> **让 Agent 自己决定自己有没有权限。**

这是不合理的。

应该是：

```text
LLM
 ↓
提出 Action
 ↓
Policy Engine
 ↓
判断风险
 ↓
决定是否需要 Human
```

即：

> **LLM 可以建议，但 Policy 才拥有最终控制权。**

---

# 二十三、因此生产级 HITL 最好设计成“三层防线”

### 第一层：LLM

```text
“我要调用 refund”
```

---

### 第二层：Policy Engine

```text
refund
amount = $5,000
risk = HIGH

→ require_human = true
```

---

### 第三层：Human

```text
Approve
```

最后才：

```text
Tool
 ↓
refund()
```

所以：

```text
LLM
 ↓
Policy
 ↓
Human
 ↓
Tool
```

这比：

```text
LLM
 ↓
Human?
 ↓
Tool
```

可靠很多。

---

# 二十四、HITL 和 Re-plan 怎么结合？

这也是 LangGraph 很漂亮的地方。

例如：

```text
Planner
 ↓
Plan v1
 ↓
Human
 ↓
“不要调研 Google，换成 Microsoft”
 ↓
Re-plan
 ↓
Plan v2
 ↓
Execute
```

或者：

```text
Executor
 ↓
发现退款金额超过政策
 ↓
Evaluator
 ↓
Human
 ↓
“最多只能退 $3,000”
 ↓
Re-plan
 ↓
Execute
```

所以 Human 的反馈可以成为：

```text
Observation
```

重新进入 Planner。

最终：

```text
Human
 ↓
Feedback
 ↓
State
 ↓
Planner
 ↓
New Plan
```

这是一种非常强的模式。

---

# 二十五、HITL 最值得放的 6 个位置

如果你实际设计系统，可以按照这个优先级考虑。

### Level 1：Plan Approval

适合：

```text
长任务
高成本任务
目标不明确
```

---

### Level 2：Sensitive Task Approval

适合：

```text
退款
删除
修改
发布
```

---

### Level 3：Sensitive Tool Approval

适合：

```text
send_email()
delete_database()
transfer_money()
```

---

### Level 4：Artifact Review

适合：

```text
合同
报告
公告
邮件
代码
```

---

### Level 5：Exception Handling

适合：

```text
Agent 卡住
连续失败
违反规则
无法满足约束
```

让人决定：

```text
Retry / Skip / Re-plan / Cancel
```

---

### Level 6：Final Approval

适合：

```text
对外发布
正式提交
付款
签署
```

---

# 二十六、我最推荐的生产策略

不要做：

```text
所有 Task 都人工审批
```

也不要做：

```text
完全自动
```

而是：

```text
                  Risk
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
      LOW        MEDIUM       HIGH
       │           │           │
    Automatic    Policy      Human
                   │
             ┌─────┴─────┐
             ↓           ↓
          Auto       Human
```

也就是说：

> **HITL 应该是一个动态的风险控制机制，而不是固定的 Workflow Node。**

---

# 二十七、最后从架构角度理解 LangGraph HITL

如果把整个东西抽象一下：

```text
                   ┌─────────────┐
                   │    State    │
                   └──────┬──────┘
                          │
                          ▼
                       Planner
                          │
                          ▼
                     Scheduler
                          │
                          ▼
                      Executor
                          │
                          ▼
                    Policy Engine
                          │
              ┌───────────┴───────────┐
              │                       │
           Allowed                Approval
              │                       │
              │                   Interrupt
              │                       │
              │                    Human
              │                       │
              │                Approve / Edit
              │                       │
              └───────────┬───────────┘
                          ▼
                         Tool
                          │
                          ▼
                       Result
                          │
                          ▼
                      Evaluator
                          │
                    ┌─────┴─────┐
                    ▼           ▼
                  Done       Re-plan
```

这时候你会发现：

**HITL 并不是 Plan-and-Execute 的一个附属功能。**

它实际上解决的是：

> **Agent 如何在自主性（Autonomy）和可控性（Control）之间取得平衡。**

---

# 二十八、如果让我设计一个真正生产级 LangGraph Agent

我会把核心模块定成：

```text
Agent Runtime
│
├── Planner
│
├── Plan Validator
│
├── Scheduler
│
├── Executor
│
├── Evaluator
│
├── Re-planner
│
├── Policy Engine
│
├── Human Approval
│
├── Checkpoint Store
│
├── Memory
│
├── Artifact Store
│
├── Tool Registry
│
├── Budget Manager
│
└── Observability
```

其中最值得注意的是这几个关系：

```text
Planner
  ↓
“我想做什么”

Scheduler
  ↓
“现在做什么”

Executor
  ↓
“怎么做”

Policy Engine
  ↓
“允许不允许做”

Human
  ↓
“高风险情况下最终由谁决定”

Evaluator
  ↓
“做得对不对”

Re-planner
  ↓
“如果不对，下一步怎么办”
```

这套分工一旦理解了，**LangGraph 的 HITL、interrupt、checkpoint、conditional edge、subgraph 等功能就不再是零散 API，而会变成一套非常清晰的生产架构。**

尤其是要记住一句：

> **生产级 Agent 不是“尽可能让 AI 自主”，而是“让 AI 在明确的权限边界内尽可能自主”。**

这也是为什么 **HITL + Policy Engine + Checkpoint/Resume** 往往是企业级 Agent 和 Demo Agent 之间非常明显的一条分界线。
