# Deep Research 项目 · 简历版本规划

## Context（背景）

用户要把 `backend/docs/html/` 下的 DeepResearch 多智能体深度研究后端写进个人简历，目标岗位是 **AI 应用 / Agent 工程师**，项目在简历中定位为 **多个项目经历之一（紧凑展示）**，叙事风格采用 **STAR 法则**，差异化亮点以 **多智能体编排 + HITL 断点续传为主、KB 知识库为次、其余作补充**。

最终交付需在 **3/4 A4 纸**篇幅内（≈ 11 号字体 1.2 行间距下 500–650 字），容纳项目名/角色/时间、技术栈、项目简介、4–5 条核心亮点。

我已经深度阅读过该项目 21 份文档，掌握所有可量化亮点与技术细节，本规划直接给出最终版本与多种侧重变体。

---

## 简历项目设计原则

### 1. 字数与版面控制（硬约束）

| 区块 | 建议字数 | 作用 |
|------|---------|------|
| 项目标题行 | 30 字 | 项目名 · 角色 · 时间 |
| 项目简介 | 50 字 | 一句话说清「是什么 + 解决什么」 |
| 技术栈行 | 25 字 | 5–8 个核心栈（逗号分隔） |
| Bullet 1（主亮点） | 110 字 | 多智能体编排 + HITL 断点续传 |
| Bullet 2（次亮点） | 95 字 | KB 知识库闭环（Milvus 长期记忆） |
| Bullet 3（工程亮点） | 95 字 | 并行研究 + 多重防御保险 |
| Bullet 4（性能亮点） | 95 字 | 流式响应 + 异步任务调度 |
| Bullet 5（可选亮点） | 50 字 | LLM-as-Judge 评估框架（短） |
| **合计** | **≈ 550 字** | 适配 3/4 A4 |

### 2. STAR 法则映射（每条 bullet）

| 字母 | 含义 | 简历中如何呈现 |
|------|------|--------------|
| **S** Situation | 业务背景 / 用户痛点 | 1 句"通常/往往/为解决…"开头 |
| **T** Task | 技术挑战 / 设计目标 | 隐含在动词"实现/设计/构建"中 |
| **A** Action | 关键设计 / 技术决策 | 2–3 个具体技术名词串联 |
| **R** Result | 量化结果 / 工程价值 | 数字 + 时间 / 资源 / 质量提升 |

### 3. 命名建议（项目标题）

候选标题（按"AI 应用 / Agent 工程师"岗位匹配度排序）：

1. **DeepResearch · 多智能体深度研究后端**（最清晰，含产品名）
2. **DeepResearch Agent 后端 · 多智能体编排平台**（强调 Agent 平台属性）
3. **Deep Research 多智能体研究系统**（最简短，去品牌化）

**推荐 #1**：保留 品牌名体现产品意识；副标题点明"多智能体 + 深度研究"两个关键词，匹配 Agent 工程师岗位 JD 高频词。

---

## 最终推荐版本（A：主推 · STAR 完整版 · ≈ 550 字）

### 项目标题行
> **DeepResearch · 多智能体深度研究后端** | 独立开发者 | 2025.05 – 至今

### 项目简介
> 基于 LangGraph 的多智能体深度研究平台，支持研究计划 HITL 确认、KB 长期记忆、SSE 流式响应与异步任务调度。

### 技术栈
> Python 3.11 · LangGraph · FastAPI · Redis Stream · Milvus · DashScope MCP · SSE · async/await

### 核心亮点（5 条 STAR 格式）

**① 多智能体编排 + HITL 断点续传**
深度研究需用户多次中断与补充需求。基于 LangGraph 设计「主图 + ResearchAgent / WriterAgent 双子图」架构，引入"透传 lambda 节点 + AsyncRedisSaver"实现 HITL 暂停与 7 天 TTL 断点续传，二次提交 `generate_plan` 节点幂等早退。**结果**：用户等待计划确认阶段零线程/LLM 资源占用，节省至少 1 次大模型调用。

**② KB 知识库闭环（Milvus 长期记忆）**
多任务检索内容大量重复、浪费 token。设计"读旧写新"闭环：研究前从 Milvus 召回已有 facts 注入 prompt；研究后 `FactExtractor` 把摘要拆为原子事实并按 `fact_category` 配置 TTL（market_data 7d / technology 180d / historical ∞）后写入。**结果**：跨任务复用知识，置信度按 `max(0.3, 1 - age/(max_age*2))` 衰减。

**③ 并行研究 + 四重防御保险**
串行搜索慢、LLM 自评易偏差。ResearchAgent 用 `Send API + operator.add reducer` 把 N 次搜索从 O(Nt) 降为 O(t)；WriterAgent 设计四重退出保险（ready_for_polish / score≥8.0 / score≥6.0+revision≥1 / max_revisions）防御 Critic 自评偏差。**结果**：研究时间提速 2–3 倍，写作循环可控退出。

**④ 流式响应 + 异步任务调度**
研究任务长（分钟级），需实时反馈。设计 6 层流式链路（LLM → `astream_step` → `on_token` → `emit_token` → Redis XADD → SSE），后端用 Redis Stream + Consumer Group 异步消费；`search_cache` 模块内置内存降级保证 Redis 故障不影响主流程。**结果**：用户实时看到流生成 token；任务异常自动 XACK + 24h TTL 自清理。

**⑤ LLM-as-Judge 评估框架（旁路观察）**
迭代需量化质量指标。实现端到端 5 维度（事实准确性/覆盖度/逻辑/时效/引用）+ 组件级 7 维度独立打分；`Judge._call` 3 次重试 + Pydantic 强类型校验；`monkey-patch` 拦截 `WebSearchAgent.step` 捕获原始检索结果。**结果**：评估不修改主链路任何文件，可直接重跑对比分数变化。

---

## 备选版本 B：极致精简版（≈ 380 字 · 占 1/2 A4）

如版面紧张，可只保留前 3 条 bullet 并压缩：

> **DeepResearch · 多智能体深度研究后端** | 独立开发者 | 2025.05 – 至今
>
> 基于 LangGraph 的多智能体深度研究平台，支持 HITL 计划确认、KB 长期记忆与 SSE 流式响应。
>
> **技术栈**：Python · LangGraph · FastAPI · Redis Stream · Milvus · MCP
>
> - **多智能体编排 + HITL**：LangGraph 主图 + ResearchAgent/WriterAgent 双子图；透传 lambda 节点 + AsyncRedisSaver（7 天 TTL）实现断点续传，二次提交节点幂等早退，用户等待阶段零后端资源占用。
> - **KB 闭环（Milvus）**：研究前 Milvus 召回已有 facts 注入 prompt，FactExtractor 抽取新事实按 category 写入（TTL 7d~365d），置信度按 age 衰减且下限 0.3，实现跨任务长期记忆。
> - **并行 + 多重保险**：Send API + operator.add reducer 把 N 次并行搜索从 O(Nt) 降为 O(t)；WriterAgent 设计 4 重退出保险防御 Critic 自评偏差，研究/写作循环可控退出。

---

## 备选版本 C：突出量化版（数字党最爱 · ≈ 580 字）

把每条 bullet 的 Result 部分数字前置，适合数据导向型岗位筛选：

> **DeepResearch · 多智能体深度研究后端** | 独立开发者 | 2025.05 – 至今
>
> 基于 LangGraph 的多智能体深度研究后端，含 21 份配套架构文档；支持 HITL 计划确认、KB 长期记忆、流式 SSE 响应与异步任务调度。
>
> **技术栈**：Python 3.11 · LangGraph · FastAPI · Redis Stream · Milvus · DashScope MCP · SSE
>
> - **HITL 断点续传**：基于"透传 lambda 节点 + AsyncRedisSaver（7 天 TTL）"实现研究计划阶段暂停与恢复；二次提交 `generate_plan` 节点检测 `plan_status=confirmed` 即返回空字典，跳过 1 次 LLM 调用。
> - **并行研究提速**：用 LangGraph `Send API + operator.add reducer` 把 N 个查询并行化，单轮研究时间从 O(Nt) 降为 O(t)，实际提速 2–3 倍。
> - **KB 闭环降本**：Milvus 召回历史 facts，研究前注入 prompt；研究后 `FactExtractor` 抽取新事实按 `fact_category`（market_data 7d / technology 180d / historical 365d）写入；置信度衰减公式 `max(0.3, 1-age/(max_age*2))` 保证旧事实仍有 30% 可用价值。
> - **流式 + 异步**：6 层流式链路（LLM → `astream_step` → `on_token` → `emit_token` → Redis XADD → SSE）实现 token 级实时推送；Redis Stream + Consumer Group 异步消费，4 类 Redis Key 设计 + search_cache 内存降级。
> - **LLM-as-Judge 评估**：端到端 5 维 + 组件级 7 维独立打分；`Judge._call` 3 次重试 + Pydantic 校验；`monkey-patch` 拦截原始检索结果；评估模块不修改主链路任何文件。

---

## 关键文件参考

简历内容均来源于此前阅读过的文档（无需重新读文档即可完成）：

- `backend/docs/html/main-graph.html` — 主图架构（亮点 ①）
- `backend/docs/html/hitl_awaiting_plan_confirmation.html` — HITL 暂停三要素（亮点 ①）
- `backend/docs/html/research-agent.html` — KB 闭环 + 并行扇出（亮点 ②③）
- `backend/docs/html/writer-agent.html` — 四重退出保险（亮点 ③）
- `backend/docs/html/base-agent.html` — 6 层流式链路（亮点 ④）
- `backend/docs/html/process-one-task.html` — Redis Stream 异步消费（亮点 ④）
- `backend/docs/html/redis-operations.html` — 4 类 Redis Key + 内存降级（亮点 ④）
- `backend/docs/html/fact-store.html` — 衰减公式 + TTL 配置（亮点 ②）
- `backend/docs/html/eval/index.html` — LLM-as-Judge 框架（亮点 ⑤）
- `backend/docs/html/docs-map.html` — 21 份文档地图（参考完整性背书）

---

## 验证方式（落地检查清单）

实施简历时按下列清单逐项核对：

- [ ] **总字数** ≤ 600 中文字符（3/4 A4 安全线 11 号字体）
- [ ] **STAR 完整度** 每条 bullet 必须出现动词（设计/实现/构建/引入）+ 技术名词 + 数字结果
- [ ] **差异化亮点顺序** bullet ① = 多智能体+HITL，bullet ② = KB，bullet ③ = 并行+保险，bullet ④ = 流式+异步，bullet ⑤ = 评估（按用户优先级）
- [ ] **关键词命中** 必含「LangGraph」「HITL」「Milvus」「Redis Stream」「FastAPI」「MCP」「SSE」「多智能体」中至少 5 个
- [ ] **可量化项** 每条 bullet 至少 1 个具体数字（7d TTL / O(Nt)→O(t) / 6 层链路 / 4 重保险 / 5+7 维度）
- [ ] **诚实底线** 仅使用文档中已验证的事实，不臆造未实现功能或未跑过的指标
- [ ] **英文友好** 项目名/角色/时间行用英文（视投递地区调整），技术栈英文，bullet 可中英混合
- [ ] **排版一致性** 整份简历中所有项目条目使用相同 bullet 符号（• 或 ▸）、相同字体大小、相同行距

---

## 落地建议

1. **优先使用版本 A**（STAR 完整版），覆盖面最广、叙事最完整，适合中高端 Agent 工程师岗位。
2. **如投递初创公司/AI 创业团队**，可选用**版本 C**（量化版），数字党招聘方更喜欢看具体数字。
3. **如投递大厂/外企**，可选用**版本 B**（精简版），英文版项目名 + 紧凑 bullet 风格更受 HR 青睐。
4. **配套 GitHub**：** 简历写完后，把 `docs/html/docs-map.html` 作为项目 README 的入口或 wiki 主页，配合源码截图可让招聘方快速理解项目全貌（21 份文档 6 大模块）。
5. **配套面试**：** 简历中每个数字都准备好被追问，准备 STAR 详版口述（如"7 天 TTL 是为了配置的""为什么为什么不用其他方案"）。