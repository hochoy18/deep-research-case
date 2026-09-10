# ZhiPo DeepResearch · 简历核心技术要点弹药库

> 📌 用途：从 21 份项目文档提炼出的可投递简历的技术要点集合。每条要点都标注了：
> - **【优先级】**：核心 / 次要 / 补充（对应简历中 bullet 顺序）
> - **【出处】**：哪份文档可查证（避免臆造）
> - **【可量化】**：可作为简历中数字的硬指标
> - **【关键词】**：JD 命中关键词

---

## 🏆 A. 多智能体编排（优先级：核心 · 必写）

### A1. LangGraph 多图架构
- **要点**：主图 + ResearchAgent 子图 + WriterAgent 子图三层嵌套
- **可量化**：主图 6 节点 + 6 条边（含 2 条条件边）
- **关键词**：LangGraph / StateGraph / 多智能体 / 子图嵌套 / subgraphs
- **出处**：`main-graph.html` / `research-agent.html` / `writer-agent.html`

### A2. LangGraph Send API 并行扇出
- **要点**：ResearchAgent 用 `Send(_WEB_SEARCH, {...})` 把 N 个并行查询分发到多个 `_web_search` 实例
- **可量化**：N 次搜索从 O(Nt) 降为 O(t)（提速 2–3 倍）
- **关键词**：Send API / 并行扇出 / operator.add reducer
- **出处**：`research-agent.html`（_fan_out_to_web_search 节点，line 170-175）

### A3. 状态机驱动 + reducer 自动累积
- **要点**：节点间通过 TypedDict `OverallState` 共享数据；`operator.add` reducer 让并行副本的输出自动累积到主 state
- **可量化**：3 个并行字段自动合并（sources_gathered / web_search_result / search_query）
- **关键词**：TypedDict / reducer / 状态机
- **出处**：`research-agent.html` / `state.py`

---

## 🎯 B. HITL 断点续传（优先级：核心 · 必写）

### B1. 透传节点 + 无出边 + AsyncRedisSaver 三要素
- **要点**：用 `lambda state, config: state` 透传节点 + 无出边实现"图自然结束"暂停；AsyncRedisSaver 自动 checkpoint
- **可量化**：用户等待计划确认阶段**零线程/LLM 资源**占用
- **关键词**：HITL / AsyncRedisSaver / 断点续传 / checkpoint
- **出处**：`main-graph.html` / `hitl_awaiting_plan_confirmation.html`

### B2. Redis Checkpoint 持久化
- **要点**：用 Redis 作为 LangGraph checkpoint 后端，断线/重启后能加载原 state 继续
- **可量化**：7 天 TTL + `refresh_on_read=True`
- **关键词**：AsyncRedisSaver / TTL / refresh_on_read
- **出处**：`redis-operations.html` / `astream-explained.html`

### B3. 二次提交幂等早退
- **要点**：二次 invoke 时 `generate_plan` 检测 `plan_status=confirmed` 直接 `return {}` 跳过
- **可量化**：**节省至少 1 次 LLM 调用**（与首次 submit 对比）
- **关键词**：幂等 / 状态机 / plan_status
- **出处**：`main-graph.html`（generate_plan 节点，line 40-85）

### B4. plan_status 隐式契约
- **要点**：前端必须 append HumanMessage + 改 `plan_status="confirmed"` 才能二次 invoke 触发研究
- **可量化**：实现 vs LangGraph 显式 `interrupt_before + Command(resume)` 方案
- **关键词**：契约设计 / 状态字段 / 前端协同
- **出处**：`hitl_awaiting_plan_confirmation.html` / `hitl_interaction_flow.md`

---

## 📚 C. KB 知识库闭环（优先级：次要重点 · 强推荐）

### C1. Milvus 长期记忆 + 读旧写新闭环
- **要点**：研究前 Milvus 召回已有 facts 注入 prompt；研究后 FactExtractor 抽取新 facts 写入
- **可量化**：跨任务复用知识，避免重复检索
- **关键词**：Milvus / 向量库 / KB / 长期记忆 / RAG
- **出处**：`kb/index.html` / `fact-store.html` / `fact_extractor.html`

### C2. 5 阶段 query 流水线
- **要点**：召回 → Reranker 精排 → 时效过滤 → 置信度衰减 → 返回 hits
- **可量化**：召回 `max(top_k*3, 20)`；置信衰减下限 0.3
- **关键词**：Milvus / IVF_FLAT / Reranker / COSINE 距离
- **出处**：`fact-store.html`（query 5 阶段）

### C3. 4 种 lifecycle 模式连续光谱
- **要点**：off / inform / freshness / lifecycle 四种模式按环境变量切换
- **可量化**：同一 codebase 4 种 KB 集成策略可插拔
- **关键词**：lifecycle / 可插拔 / 配置驱动
- **出处**：`kb/index.html` / `lifecycle.py`

### C4. 5 类 fact_category 精细化 TTL
- **要点**：market_data 7d / product_info 30d / strategy 60d / technology 180d / historical ∞
- **可量化**：5 类 × 4 生命周期模式 = 20 种策略组合
- **关键词**：TTL / 时效 / 精细化
- **出处**：`lifecycle.py` / `kb/index.html`

### C5. 置信度衰减公式
- **要点**：`decay_factor = max(0.3, 1.0 - age_days / (effective_max_age * 2))`
- **可量化**：旧事实保留 30% 最低价值（不会硬过期到 0）
- **关键词**：置信度衰减 / 数学公式 / 评分机制
- **出处**：`fact-store.html`（衰减公式图）

### C6. 失败不抛异常哲学
- **要点**：FactExtractor 任何路径失败都返回 `[]`，绝不抛异常
- **可量化**：KB 写失败不阻塞 ResearchAgent 主 
- **关键词**：优雅降级 / 容错设计 / fail-safe
- **出处**：`fact_extractor.html`（7 步流程 + 多层 try/except）

### C7. Embedding 智能重试
- **要点**：3 次重试，401/403/400 不重试（永久错误），429/5xx/网络错退避重试
- **可量化**：3 次重试 + 智能分类减少无效重试
- **关键词**：重试策略 / 异常分类 / 退避
- **出处**：`fact-store.html`（_embed 流程）

---

## ⚡ D. 流式响应 + 异步调度（优先级：重要补充）

### D1. 6 层流式响应链路
- **要点**：LLM → `astream_step` → `on_token` → `emit_token` → Redis XADD → SSE → 浏览器
- **可量化**：6 层链路，每层都有 try/except 隔离
- **关键词**：流式响应 / SSE / Redis Stream / token 推送
- **出处**：`astream-explained.html` / `base-agent.html`

### D2. Redis Stream + Consumer Group 异步消费
- **要点**：用 XREADGROUP 阻塞 5s, COUNT=1, `>` 游标；XACK 在 finally 中保证不丢消息
- **可量化**：5s 阻塞窗口，task 24h EXPIRE 自动清理
- **关键词**：Consumer Group / 任务队列 / XREADGROUP
- **出处**：`redis-operations.html` / `process-one-task.html`

### D3. 4 类 Redis Key 设计
- **要点**：session（Hash，24h）/ research:tasks（Stream）/ research:events:{id}（Stream）/ search_cache（String，1h）
- **可量化**：4 类 Key × 不同 TTL × 不同 MAXLEN
- **关键词**：Redis 数据建模 / TTL / MAXLEN
- **出处**：`redis-operations.html`

### D4. search_cache 内存降级
- **要点**：唯一带降级的模块，Redis 不可用 → 内存 dict + Lock
- **可量化**：Redis 故障不影响主流程
- **关键词**：优雅降级 / 容错 / 缓存
- **出处**：`search_cache.py` / `redis-operations.html`

### D5. 子图事件命名空间穿透 + 节点名翻译
- **要点**：`subgraphs=True` 让 astream 穿透子图；`_SUBGRAPH_EVENT_MAP` 把内部节点名翻译为前端协议名
- **可量化**：3 个节点名翻译（generate_queries → generate_query 等）
- **关键词**：subgraphs / 命名空间 / 协议转换
- **出处**：`astream-explained.html`

---

## 🛡️ E. 多重防御保险（优先级：技术亮点 · 强烈推荐）

### E1. WriterAgent 四重退出保险
- **要点**：ready_for_polish / score≥8.0 / score≥6.0+revision≥1 / max_revisions 四层防御 Critic 自评偏差
- **可量化**：四重条件 OR，任一命中即退出
- **关键词**：防御编程 / 自评偏差 / 多重保险
- **出处**：`writer-agent.html`（_route_after_critic，line 181-233）

### E2. ResearchAgent 双重退出保险
- **要点**：`is_sufficient OR research_loop_count >= max_research_loops`
- **可量化**：防止研究循环死循环 + LLM 自评失误
- **关键词**：循环控制 / 死循环防护
- **出处**：`research-agent.html`（_route_after_critique）

### E3. _draft 节点双角色
- **要点**：首版 vs 修订通过 `critic_feedback` 区分，`is_revision = bool(feedback)`
- **可量化**：减少节点数量（合并 2 个节点为 1 个）
- **关键词**：节点复用 / 状态分支
- **出处**：`writer-agent.html`（_draft 节点）

---

## 🤖 F. Agent 框架与基础能力（优先级：工程基础 · 推荐）

### F1. 4 层类继承
- **要点**：Agent → JsonAgent / MCPAgent → WebSearchAgent
- **可量化**：629 行 base_agent.py，5 大组件
- **关键词**：OOP / 继承 / 抽象基类
- **出处**：`base-agent.html`

### F2. RateLimiter 令牌桶
- **要点**：全局单例，默认 12 QPS（环境变量 `WEB_SEARCH_MAX_QPS`）
- **可量化**：async/sync 双接口，避免 429 限流
- **关键词**：令牌桶 / 限流 / 单例
- **出处**：`base-agent.html`（RateLimiter，line 26-80）

### F3. _retry_with_classified_errors
- **要点**：3 次重试 + Permanent/Transient 异常分类 + 线性增长延迟
- **可量化**：Permanent 直接抛、Transient 重试、未知保守重试
- **关键词**：重试 / 异常分类 / 退避
- **出处**：`base-agent.html`（line 109-164）

### F4. JsonAgent 强制 JSON 输出
- **要点**：用 Pydantic TypedDict 约束 LLM 输出，3 层 fallback 抽取 JSON
- **可量化**：100% 结构化输出保证
- **关键词**：结构化输出 / Pydantic / 校验
- **出处**：`base-agent.html`（JsonAgent，line 308-317）

### F5. 流式降级机制
- **要点**：3 次流式失败 → 降级非流式 `astep`
- **可量化**：用户体验与稳定性平衡
- **关键词**：降级 / 容错 / 流式
- **出处**：`base-agent.html`（astream_step，line 238-295）

---

## 🔌 G. MCP 与外部集成（优先级：技术亮点 · 选写）

### G1. DashScope MCP 集成
- **要点**：调用 dashscope `Application.call` API 进行 web search + 摘要
- **可量化**：5 类 MCP 异常分类处理（RateLimit/Auth/AccessDenied/Server/Parse）
- **关键词**：MCP / DashScope / 异常分类
- **出处**：`base-agent.html` / `MCPAgent`

### G2. WebSearchAgent 4 步流程
- **要点**：缓存查找 → 速率限制 → MCP 调用 → 缓存写入
- **可量化**：3 层 JSON 解析兼容多种响应路径
- **关键词**：缓存 / 限流 / MCP / 解析
- **出处**：`base-agent.html`（WebSearchAgent，line 407-622）

---

## 🧪 H. LLM-as-Judge 评估框架（优先级：差异化亮点 · 强推荐）

### H1. 端到端 5 维 + 组件级 7 维独立打分
- **要点**：e2e 5 维（事实准确性/覆盖度/逻辑/时效/引用）+ 组件级 7 维（plan/queries/summarization/critique/citations/plan reflection）
- **可量化**：12 个评分维度，全维度独立 Pydantic 校验
- **关键词**：LLM-as-Judge / 评估框架 / 多维度
- **出处**：`eval/index.html`

### H2. 旁路观察者设计
- **要点**：评估框架不修改 application 主链路任何文件，只 import 并调用
- **可量化**：可直接重跑对比分数变化
- **关键词**：旁路 / 非侵入 / 可重入
- **出处**：`eval/index.html`（设计哲学）

### H3. monkey-patch 拦截原始检索结果
- **要点**：`_CaptureCtx` 通过 monkey-patch `WebSearchAgent.step` 捕获原始搜索结果
- **可量化**：弥补 web_search 节点只存摘要的缺陷
- **关键词**：monkey-patch / 拦截 / 黑盒测试
- **出处**：`eval/index.html`（_CaptureCtx 机制）

### H4. Judge._call 3 次重试 + Pydantic 校验
- **要点**：LLM 调用 + Post.extract_pattern 抽 json + Pydantic 强类型校验 + 1-5 分自动 clamp
- **可量化**：3 次重试 + 强类型校验保证评分稳定性
- **关键词**：评分重试 / 强类型 / 自动 clamp
- **出处**：`eval/index.html`

### H5. 测试集设计
- **要点**：10 个 topic = 5 基础（科技/金融/政策/产业/方法论）+ 5 需求澄清（带 user_feedback）
- **可量化**：覆盖 5 大领域 + HITL 关键场景
- **关键词**：测试集 / 覆盖度 / 场景
- **出处**：`eval/test_set.json`

### H6. 评分量纲可视化
- **要点**：1.0-1.9 红（不可用）/ 2.0-2.9 橙（较差）/ 3.0-3.9 青（合格）/ 4.0-5.0 绿（优秀）
- **可量化**：4 段色彩化评分，HR 可一眼看懂质量
- **关键词**：评分可视化 / 量纲 / 色阶
- **出处**：`eval/index.html`

---

## 🎨 I. Prompt 工程（优先级：可选补充 · 选写）

### I1. 五步澄清循环
- **要点**：解构 → 模糊度评估 → 智能默认项 → 迭代可视化 → 锁定确认
- **可量化**：5 步结构化对话约束 Agent 行为
- **关键词**：Prompt 工程 / 结构化对话 / 澄清循环
- **出处**：`prompts/plan_instructions.html`

### I2. 专报五大关键要素
- **要点**：Subjects / Opponent's Strategy / Risk Assessment / Scope & Boundaries / Output Format
- **可量化**：5 维度需求拆解模板
- **关键词**：需求分析 / 模板 / 关键要素
- **出处**：`prompts/plan_instructions.html`

### I3. 进度条设计
- **要点**：0-30% 模糊期 / 30-70% 部分澄清 / 70-95% 大部分澄清 / 95-100% 锁定
- **可量化**：让用户感知推进，避免挫败感
- **关键词**：UX / 进度可视化 / 用户体验
- **出处**：`prompts/plan_instructions.html`

### I4. confirm_plan 双路径设计
- **要点**：关键词（开始研究/需求确认）短路 + LLM JsonAgent/PlanReflection 兜底
- **可量化**：3 种确认路径（显式/兜底/隐式）都默认推进（乐观偏向）
- **关键词**：意图识别 / 兜底 / 乐观偏向
- **出处**：`main_graph/confirm_plan.html`

---

## 🛠️ J. 工程实践（优先级：加分项 · 选写）

### J1. 配置回退链
- **要点**：`EMBEDDING_BASE_URL → LLM_BASE_URL`，`EMBEDDING_API_KEY → APP_TOKEN`
- **可量化**：避免重复配置
- **关键词**：配置管理 / fallback / DRY
- **出处**：`fact-store.html`

### J2. sentinel 单例模式
- **要点**：KB 初始化失败时 `_kb_store = False`，后续调用直接返回 None
- **可量化**：与 None 区分（False vs None）
- **关键词**：单例 / sentinel / 容错
- **出处**：`research-agent.html`（_get_kb_store）

### J3. add_messages reducer
- **要点**：消息列表自动追加，避免重复
- **可量化**：未知类型丢弃但保留 id，避免 reducer 报错
- **关键词**：reducer / 消息去重
- **出处**：`process-one-task.html`

### J4. 短链接 URL 双向映射
- **要点**：LLM 用短 URL 节省 token；KB 入库前反向还原真实 URL
- **可量化**：节省 prompt token；避免 KB 存不可解析引用
- **关键词**：token 优化 / URL 映射
- **出处**：`writer-agent.html` / `subagent_writer/web_search.html`

### J5. async/sync 双接口
- **要点**：RateLimiter 提供 `acquire()` 和 `aacquire()` 双接口
- **可量化**：覆盖同步/异步调用方
- **关键词**：双接口 / 兼容性 / 异步
- **出处**：`base-agent.html`

---

## 📊 K. 项目规模数字（优先级：项目背书 · 必写至少 1 个）

- 📁 **21 份架构文档** + 1 份文档地图（docs/html/）
- 🐍 **Python 3.11+**，依赖 16+ 个核心包
- 📦 **总代码量 ≈ 3500+ 行**（graph.py 197 + base_agent.py 629 + research_agent.py 343 + writer_agent.py 313 + kb/* 600+ + app.py + task_queue.py + eval/* 等）
- 🧪 **10 个测试 topic**（5 基础 + 5 需求澄清）
- 🎨 **6 张 Mermaid 图** + 21 张架构表 + 5 大子模块
- 🔄 **4 类 Redis Key** + 5 类 MCP 异常 + 4 类 KB 异常
- 📐 **12 项工程亮点** + **3 大设计哲学**（优雅降级/失败不抛异常/旁路观察者）
- ⏱️ **支持从几十秒到分钟级**任务流式执行

---

## 🎯 L. 简历组合建议

### L1. 应届/初级（突出广度）
- 选 5–6 个 C/D/F 类次要点 + 1 个 K 项目规模数字

### L2. 中级工程师（突出深度）
- 选 1 个 A + 1 个 B + 2 个 C + 1 个 E + 1 个 D（10–12 个要点）

### L3. 高级/资深（突出设计）
- 选 A1+A2（多智能体深度）+ B1+B3（HITL 设计）+ C1+C3+C5（KB 完整设计）+ E1（多重保险）+ H1+H2（评估体系）+ 1 个 K

### L4. 应聘 AI 应用/Agent 岗（推荐组合）
- A1 多智能体架构 + A2 Send API 并行 + B1 HITL 三要素 + C1 KB 闭环 + E1 四重保险 + H1 评估框架

---

## ✅ 使用方法

1. **挑选要点**：根据目标岗位 JD 关键词，从 A–J 类别中挑选匹配的要点
2. **STAR 包装**：按已批准的简历版本 A 的格式包装成 STAR 风格 bullet
3. **量化优先**：每条 bullet 至少 1 个具体数字（参考每个要点的"可量化"项）
4. **诚实底线**：仅引用"出处"中标注的实际文档，不臆造
5. **关键词命中**：根据 JD 反推需要哪些关键词，从"关键词"字段挑选

完整 STAR 包装示例见 `/Users/cai.he/.claude/plans/3-4-a4-curried-pearl.md` 中的"最终推荐版本 A"。