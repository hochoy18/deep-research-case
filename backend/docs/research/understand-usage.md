# /understand 插件使用说明

> 基于 [Egonex-AI/Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) 与 [understand-anything.com](https://understand-anything.com/) 的官方资料整理。
> 文档版本：2026-09-01  ·  插件主仓版本：1.x.x（771+ commits）  ·  License：MIT

---

## 一、什么是 /understand

`/understand` 是由 **EgonexAI（原 Lum1104）** 开发的 Claude Code 插件，标语为：

> **Graphs that teach > graphs that impress**（"会教人的图谱，胜过只会炫技的图谱"）

它把任意代码库、知识库或文档转化为一张**可探索、可搜索、可对话的交互式知识图谱**，用一个多 Agent 流水线扫描你的项目，抽取每一个文件、函数、类和依赖，再用 React + React Flow 搭建的 Web Dashboard 把图谱可视化。

与传统的"代码结构图"不同，`/understand` 的核心理念是：

| 其他工具 | Understand Anything |
|---|---|
| 只画图：files / functions / edges | 把代码映射到**真实业务域、流程、步骤** |
| 一张没有人读懂的"毛球图"（hairball） | 用**平实语言**解释每个节点，并提供**引导式学习路径** |
| 单语言，偏代码 | **26+ 种文件类型**，统一一张图（Dockerfile、Terraform、SQL、Markdown…） |

适用人群：

- **新人开发**：被陌生代码淹没，需要逐步引导式 Tour
- **产品经理 / 设计师**：不读代码也能看懂系统如何工作，直接问"支付流程怎么走？"
- **资深开发**：跳进新项目时，借助图谱快速建立 mental model
- **架构师**：做架构 review、改动影响面分析

---

## 二、安装

`/understand` 同时支持 **Claude Code 原生** 市场和**其他 AI 编码平台**。`docs/` 已存在；该插件在 Claude Code 下安装 30 秒搞定。

### 1. Claude Code（推荐 / 原生）

```bash
# 添加市场
/plugin marketplace add Egonex-AI/Understand-Anything

# 安装插件
/plugin install understand-anything

# 验证：跑一次
/understand
```

### 2. 一行命令安装（Codex / OpenCode / OpenClaw / Antigravity / Gemini CLI / Pi Agent / Vibe CLI / VS Code Copilot / Hermes / Cline / KIMI CLI / Trae / Nanobot / Kiro）

**macOS / Linux：**

```bash
curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash
# 想跳过交互提示，直接指定平台：
curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex
```

**Windows (PowerShell)：**

```powershell
iwr -useb https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.ps1 | iex
```

安装脚本把仓库克隆到 `~/.understand-anything/repo`，再为目标平台创建软链接。安装完成后**重启你的 CLI / IDE**。

> **调用前缀差异**：大部分平台用 `/understand`；**Codex 用 `$understand`**（用 `$` 而非 `/`）；Kiro CLI 用 `kiro-cli chat --agent understand "…"`。如果两种前缀都不识别，可以直接用自然语言说"使用 understand 技能分析这个项目"。

### 3. Cursor / VS Code + GitHub Copilot（自动发现）

只需克隆仓库然后在编辑器中打开，Cursor 通过 `.cursor-plugin/plugin.json`、VS Code Copilot v1.108+ 通过 `.copilot-plugin/plugin.json` 自动识别插件。

### 4. Copilot CLI

```bash
copilot plugin install Egonex-AI/Understand-Anything:understand-anything-plugin
```

### 5. 已支持的平台一览

| 平台 | 状态 | 安装方式 |
|---|---|---|
| Claude Code | ✅ 原生 | Plugin marketplace |
| Cursor | ✅ | Auto-discovery |
| VS Code + GitHub Copilot | ✅ | Auto-discovery |
| Copilot CLI | ✅ | Plugin install |
| Codex | ✅ | `install.sh codex` |
| OpenCode | ✅ | `install.sh opencode` |
| OpenClaw | ✅ | `install.sh openclaw` |
| Antigravity | ✅ | `install.sh antigravity` |
| Gemini CLI | ✅ | `install.sh gemini` |
| Pi Agent | ✅ | `install.sh pi` |
| Vibe CLI | ✅ | `install.sh vibe` |
| Hermes | ✅ | `install.sh hermes` |
| Cline | ✅ | `install.sh cline` |
| KIMI CLI | ✅ | `install.sh kimi` |
| Trae | ✅ | `install.sh trae` |
| Nanobot | ✅ | `install.sh nanobot` |
| Kiro CLI / IDE | ✅ | `install.sh kiro` |

### 6. 更新与卸载

```bash
./install.sh --update                           # 更新
./install.sh --uninstall                        # 卸载
./install.sh --uninstall codex                  # 卸载指定平台
```

---

## 三、四步上手 Quick Start

以 Claude Code 为例：

### Step 1：安装插件

```bash
/plugin marketplace add Egonex-AI/Understand-Anything
/plugin install understand-anything
```

### Step 2：分析你的代码库

```bash
/understand
```

多 Agent 流水线扫描整个项目，把文件 / 函数 / 类 / 依赖抽取成知识图谱，写到 `.ua/knowledge-graph.json`（旧版目录为 `.understand-anything/`，会自动兼容）。

> **Token 消耗提醒**：首次运行会分析整个代码库，对大型项目可能消耗较多 token；推荐在订阅 / 配额充足的环境执行，或切换到本地模型（Ollama 等）。后续执行**默认增量**，只重分析变更过的文件，开销大幅下降。

#### 常用参数

```bash
/understand --language zh              # 生成中文内容（节点描述 + Dashboard UI + Tour 解释）
/understand --language zh-TW           # 繁体中文（en/zh/zh-TW/ja/ko/ru）
/understand --auto-update              # 安装 post-commit 钩子，每次提交自动增量
/understand src/frontend               # 只分析子目录（超大型 monorepo）
/understand --review                   # 完整 LLM 图谱 review（默认走内置 Node 校验器）
```

`--language` 首次未指定时，会根据对话语言主动询问并把选择写入 `.ua/config.json`，之后的运行都会复用。

### Step 3：打开交互 Dashboard

```bash
/understand-dashboard
```

浏览器自动打开 Dashboard：按架构层级颜色编码，支持搜索、点击节点查看代码、关系、平实语言解释。

### Step 4：持续学习与问答

```bash
/understand-chat "How does the payment flow work?"   # 自然语言问答
/understand-diff                                     # 当前改动的 ripple-effect 分析
/understand-explain src/auth/login.ts                # 深入讲解某文件 / 函数
/understand-onboard                                  # 生成新人 onboarding 指南
/understand-domain                                   # 提取业务领域（domains/flows/steps）
/understand-knowledge ~/path/to/wiki                 # 分析 Karpathy-pattern LLM Wiki
/understand                                          # 默认增量模式：只重分析变更文件
```

---

## 四、命令 / Skill 全集

`/understand` 是入口命令，配套还有 7 个细分 Skill：

| 命令 | 作用 | 输入 | 输出 |
|---|---|---|---|
| `/understand` | 扫描代码库并构建知识图谱 | 可选 `--language` / `--auto-update` / `<path>` / `--review` | `.ua/knowledge-graph.json` |
| `/understand-dashboard` | 打开交互式 Web Dashboard | 无 | 浏览器窗口 |
| `/understand-chat "<q>"` | 对知识图谱做自然语言问答 | 问题字符串 | 对话式回答 |
| `/understand-diff` | 分析当前改动对系统的影响 | 无（自动读 git diff） | 影响面报告（`.ua/diff-overlay.json` 本地暂存） |
| `/understand-explain <path>` | 深入讲解文件 / 函数 / 模块 | 目标文件或函数路径 | 详细解释 |
| `/understand-onboard` | 生成新人入职指南 | 无 | 指南文档 |
| `/understand-domain` | 抽取业务域（domains / flows / steps） | 无 | domain-graph.json + 水平图谱视图 |
| `/understand-knowledge <wiki-path>` | 分析 LLM Wiki 知识库 | Karpathy-pattern wiki 路径 | 带社群聚类的力导向图谱 |

---

## 五、底层架构：7 个 Agent 流水线和 7 个阶段

### 5.1 多 Agent 流水线

`/understand` 调度 5 个专职 Agent，`/understand-domain` 增加第 6 个，`/understand-knowledge` 增加第 7 个：

| Agent | 职责 |
|---|---|
| `project-scanner` | 发现文件，识别语言与框架 |
| `file-analyzer` | 抽取函数、类、import，产出图谱节点和边 |
| `architecture-analyzer` | 识别架构层级 |
| `tour-builder` | 生成引导式学习路径 |
| `graph-reviewer` | 校验图谱完整性（默认内置 Node 校验；`--review` 启用完整 LLM review） |
| `domain-analyzer` | 提取业务域、流程、步骤（供 `/understand-domain`） |
| `article-analyzer` | 从 Wiki 文章抽取实体、断言、隐含关系（供 `/understand-knowledge`） |

文件分析并行执行：**最多 5 个并发 worker，每批 20–30 文件**。支持**增量更新**——基于 fingerprint 增量检测，只重分析变更过的文件。

### 5.2 Pipeline 7 个阶段

`/understand` 内部跑这 7 个阶段：

```
Phase 0   Pre-flight           → 决定 full vs. incremental，读 git commit，准备目录
Phase 0.5 Ignore Configuration → 生成 .understandignore 并等用户确认
Phase 1   SCAN                 → project-scanner：项目元信息 + 文件清单 + importMap
Phase 1.5 BATCH                → compute-batches.mjs：语义批次 + 跨批邻居映射
Phase 2   ANALYZE              → 5 路并发 file-analyzer → batch-<index>.json → merge
Phase 3   ASSEMBLE REVIEW      → assemble-reviewer：merge 后语义校验
Phase 4   ARCHITECTURE         → architecture-analyzer：layers.json
Phase 5   TOUR                 → tour-builder：tour.json
Phase 6   REVIEW               → 装配最终 KnowledgeGraph + 校验（默认 / LLM）
Phase 7   SAVE                 → 写 knowledge-graph.json + meta.json + 清理 intermediate
```

Phase 0 的关键决策：

- `--full`：全量重算
- 无现存图：全量
- `--review` 且代码未变更：只校验
- 文件有变更：增量（基于 `git diff <last>..HEAD --name-only`）

Phase 2 的关键：每个 batch 文件名必须严格匹配 `batch-<batchIndex>.json`，否则 merge 脚本会丢弃。失败重试：每个阶段失败会重试一次，第二次失败会跳过并保留部分结果，所有 warning 都会在最终报告里汇总。

### 5.3 知识图谱 Schema

#### 节点类型（13 种）

```
file:        file:<relative-path>
function:    function:<path>:<name>
class:       class:<path>:<name>
module:      module:<name>
concept:     concept:<name>
config:      config:<path>
document:    document:<path>
service:     service:<path>
table:       table:<path>:<name>
endpoint:    endpoint:<path>:<name>
pipeline:    pipeline:<path>
schema:      schema:<path>
resource:    resource:<path>
```

#### 边类型（26 种）

```
【结构】    imports, exports, contains, inherits, implements
【行为】    calls, subscribes, publishes, middleware
【数据流】  reads_from, writes_to, transforms, validates
【依赖】    depends_on, tested_by, configures
【语义】    related, similar_to
【基础设施】 deploys, serves, provisions, triggers
【Schema】  migrates, documents, routes, defines_schema
```

#### 边权重

| 边类型 | 权重 |
|---|---|
| `contains` | 1.0 |
| `inherits`, `implements` | 0.9 |
| `calls`, `exports`, `defines_schema` | 0.8 |
| `imports`, `deploys`, `migrates` | 0.7 |
| `depends_on`, `configures`, `triggers` | 0.6 |
| `tested_by`, `documents`, `provisions`, `serves`, `routes` | 0.5 |
| 其他 | 0.5 |

#### 顶层 KnowledgeGraph

```json
{
  "version": "1.0.0",
  "project": {
    "name": "...",
    "languages": ["..."],
    "frameworks": ["..."],
    "description": "...",
    "analyzedAt": "2026-09-01T...",
    "gitCommitHash": "abc123..."
  },
  "nodes": [ ... ],
  "edges": [ ... ],
  "layers": [ { "id": "layer:api", "name": "...", "description": "...", "nodeIds": [ ... ] } ],
  "tour":   [ { "order": 1, "title": "...", "description": "...", "nodeIds": [...], "languageLesson": "..." } ]
}
```

### 5.4 项目目录结构

```
understand-anything-plugin/
├── .claude-plugin/     # Plugin 清单
├── agents/             # 专职 AI Agent 定义
├── skills/             # Skill 定义（/understand, /understand-chat, ...）
├── src/                # TypeScript 源码（context-builder, diff-analyzer...）
└── packages/
    ├── core/           # 分析引擎：types / persistence / tree-sitter / search / schema / tours
    └── dashboard/      # React + TypeScript Web Dashboard
```

技术栈：**TypeScript、pnpm workspaces、React 18、Vite、TailwindCSS v4、React Flow、Zustand、web-tree-sitter、Fuse.js、Zod、Dagre**。

混合分析策略：

- **tree-sitter（确定性）**：解析 AST，抽取 imports/exports/classes
- **LLM（语义）**：生成节点 summary / tags / layer / tour

---

## 六、输出文件与目录约定

`/understand` 在当前项目下创建：

```
.ua/                              # 新目录（推荐）
├── knowledge-graph.json           # 最终知识图谱（提交到仓库供团队共享）
├── meta.json                      # 元信息：lastAnalyzedAt / gitCommitHash / version / analyzedFiles
├── config.json                    # 自动更新与语言偏好
├── .understandignore              # 忽略规则
├── intermediate/                  # 本次运行的中间产物（gitignore）
├── tmp/                           # 临时文件
└── diff-overlay.json              # /understand-diff 的本机状态（gitignore）

.understand-anything/              # 旧版数据目录（已存在则继续使用，无需迁移）
```

`.gitignore` 推荐加入：

```
.ua/intermediate/
.ua/diff-overlay.json
# 或者旧版：
.understand-anything/intermediate/
.understand-anything/diff-overlay.json
```

---

## 七、与团队共享知识图谱

图谱本身只是 JSON。提交一次，全队都能跳过完整流水线——适合 onboarding、PR review、docs-as-code。

### 需要提交

`.ua/` 目录下**除** `intermediate/` 和 `diff-overlay.json` 之外的全部文件。

### 让它保持新鲜

```bash
/understand --auto-update
```

这会装一个 post-commit Git 钩子，每次提交时**增量**更新图谱，让每个 commit 都有匹配的图谱版本。

也可以在发版前手动重跑：

```bash
/understand
```

### 大图（>10 MB）走 Git LFS

```bash
git lfs install
git lfs track ".ua/*.json"
git add .gitattributes .ua/
```

### 只读共享：用 standalone viewer

无需 Claude Code、无 LLM、无 API key，**只要 Node.js ≥ 18**：

```bash
npx https://github.com/Egonex-AI/Understand-Anything/releases/latest/download/understand-anything-viewer.tgz /path/to/analyzed/project
```

会输出一个 tokenized URL（如 `http://127.0.0.1:5173/?token=…`），从本地磁盘只读提供 Dashboard。

---

## 八、Interactive Dashboard 功能详解

`/understand-dashboard` 启动的是一个 React + React Flow 可视化界面，主要能力：

### 核心可视化

- **层级颜色图例**：按 API / Service / Data / UI / Utility 自动分组（architecture-analyzer 产出）
- **可探索交互式图谱**：拖动、缩放、点击节点查看代码、关系与平实语言解释
- **业务域视图（Domain View）**：横向图谱，展示 domains → flows → steps，把代码映射到真实业务过程
- **.ua 多种文件类型**：26+ 种（代码、配置、文档、基础设施、Schema…）

### 搜索与过滤

- **模糊 + 语义搜索**：搜 "auth" 之外，可搜"哪些部分处理认证？"——按语义返回相关节点
- **按类型、复杂度、层级过滤**
- **依赖路径查找**：找出两个组件之间的最短依赖路径
- **Persona 自适应 UI**：根据你是初级开发 / PM / 资深开发，自动调整信息密度

### 引导式 Tour

- **AI 生成学习路径**：按依赖顺序生成的 5–15 步 walkthrough
- **Onboarding 模式**：专门为新成员设计的渐进式理解流程
- **12 个语言概念注释**：泛型、闭包、装饰器等 12 种程序设计模式，在上下文出现时实时解释

### 导出与分享

- 高质量 **PNG / SVG** 导出
- 过滤后的 **JSON** 导出
- 整个图谱 JSON 提交到 Git，团队成员直接复用

### 知识库分析模式（`/understand-knowledge`）

把 Karpathy-pattern LLM wiki 指向后：

- 确定性 parser 从 `index.md` 抽取 wikilinks 和 categories
- LLM Agent 发现隐式关系、抽取实体、挖掘断言
- 输出**带社群聚类的力导向图谱**——把 wiki 变成一张互联思想图谱

### 变更影响面分析（`/understand-diff`）

提交之前看哪些模块会被影响，理解 ripple-effect：

- 自动读 git diff
- 通过 `.ua/diff-overlay.json` 在 Dashboard 上叠加受影响节点（红色高亮）
- 适合"改了 utils/xx，PR 里能告诉我哪些上层用了它吗？"这种场景

---

## 九、典型工作流

### A. 接手新项目

```bash
cd ~/work/new-project
/understand --language zh         # 第一次图谱生成
/understand-dashboard             # 打开图谱看全局
/understand-onboard               # 生成 onboarding 文档
/understand-chat "整体架构是？"   # 直接问
```

### B. 大型 monorepo

```bash
/understand src/frontend          # 限定子目录
/understand src/backend --auto-update   # 增量 + post-commit
```

### C. 提交前影响面分析

```bash
git diff                          # 编辑代码
/understand-diff                  # 看哪些模块会被影响
/understand-chat "这次改动会破坏哪些测试？"
/understand                       # 提交前手动重跑增量
git commit
```

### D. 给团队共享

```bash
git add .ua/                      # 把图谱提交到仓库
git commit -m "feat: add knowledge graph for v2 onboarding"
git push
# 同事 pull 后直接：
/understand-chat "How does X work?"   # 无需重跑流水线
```

### E. Wiki / 知识库分析

```bash
/understand-knowledge ~/notes/wiki    # 生成带聚类的知识图谱
/understand-dashboard                 # 浏览
```

---

## 十、开发与贡献

仓库是 monorepo，使用 pnpm 工作区：

```bash
# 安装所有依赖
pnpm install

# 构建 core 包
pnpm --filter @understand-anything/core build

# 跑 core 单元测试
pnpm --filter @understand-anything/core test

# 构建插件包
pnpm --filter @understand-anything/skill build

# 跑插件测试
pnpm --filter @understand-anything/skill test

# 构建 Dashboard
pnpm --filter @understand-anything/dashboard build

# 本地开发 Dashboard（Vite dev server）
pnpm dev:dashboard
```

贡献流程：

1. Fork 仓库
2. 新建分支：`git checkout -b feature/my-feature`
3. 跑测试：`pnpm --filter @understand-anything/core test`
4. 提交 + 提 PR（重大改动先开 issue 讨论）

---

## 十一、常见问题

**Q1：`/understand` 一定要连 LLM 吗？**
需要。在 Phase 2 / 4 / 5 里 file-analyzer、architecture-analyzer、tour-builder 都会调 LLM。

**Q2：怎样离线 / 用本地模型？**
可以，插件支持把模型提供方换成 Ollama 等本地推理后端，按你所用平台（Claude Code / Codex / Kiro…）的指引修改模型提供方即可。

**Q3：图谱文件多大？会拖慢仓库吗？**
单语言项目通常 < 5 MB。> 10 MB 推荐 Git LFS。提交一次后全队复用，不会再产生额外 token 成本。

**Q4：第一次跑 `token` 烧太多怎么办？**
- 限定子目录：`/understand src/<module>`
- 用本地模型
- 在小项目上先试运行熟悉流程

**Q5：和传统的"结构图"（ctags、Sourcegraph、SourceSpy）差别在哪？**
其他工具给你一张"毛球图"——只画文件 / 函数 / 边，不解释含义。`/understand` 把代码**映射到业务域**，给每个节点配平实语言 summary + tour，相当于"自带图例的活地图"。

**Q6：增量更新真的只重分析变更文件吗？**
是的。Phase 0 比较 `meta.json` 的 commit hash 与 HEAD，不一致就 `git diff --name-only`，然后只重分析变更文件所在 batch，但 `neighborMap` 仍引用未变更文件，`architecture-analyzer` 总是在完整图上重跑（避免层级漂移）。

**Q7：能在 CI 里跑吗？**
可以。`/understand` 输出 `knowledge-graph.json` 是确定性的（除 LLM 产生的 summary 外），配合 `--auto-update` 已在 commit 时自动增量，可以放到 nightly CI 任务里定期用 fresh 数据 build Dashboard。

**Q8：商业项目能用吗？**
Yes，**MIT License**，可商用，可改、可分、署名即可。

---

## 十二、相关链接

- 🏠 官网：<https://understand-anything.com/>
- 📦 主仓库：<https://github.com/Egonex-AI/Understand-Anything>
- 💬 Discord：<https://discord.gg/>（参考仓库 README）
- 🎥 社区教程：Better Stack 制作的 YouTube 演示（README 收录）
- 🏢 公司：EgonexAI（Infinite Universe, Inc.）
- 🌟 早期信息：曾在 Trendshift 拿下 GitHub Trending #1 Repository Of The Day
- 📦 viewer：`releases/latest/download/understand-anything-viewer.tgz`

---

> **TL;DR（30 秒版）**
> 1. `/plugin marketplace add Egonex-AI/Understand-Anything` + `/plugin install understand-anything`
> 2. 在你的项目根目录跑 `/understand`，等待多 Agent 流水线生成 `.ua/knowledge-graph.json`
> 3. `/understand-dashboard` 看图谱，`/understand-chat` 提问，`/understand-diff` 提交前看影响面
> 4. 把 `.ua/` 提交到 Git，让团队一起用
