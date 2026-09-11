# SSE 两种实现方式对比 · case01 vs case02

本目录用 **同一个端点集** 演示 SSE 的两种实现：

| 文件 | 端口 | 实现方式 | 依赖 |
|---|---|---|---|
| `case01_streaming_response.py` | 8001 | `fastapi.responses.StreamingResponse` | 无（FastAPI 原生） |
| `case02_event_source_response.py` | 8002 | `sse_starlette.sse.EventSourceResponse` | `sse-starlette` |
| `test_client.py` | — | 通用测试客户端（httpx） | — |

## 1. 一句话区别

> **`StreamingResponse` 是毛坯房（协议格式、headers、心跳都要自己写）**；
> **`EventSourceResponse` 是精装房（库自动格式化、自动加 header、内置 ping 心跳）。**
> 底层都是同一个 `StreamingResponse`，只是后者多包了一层 SSE 协议处理。

## 2. 同一端点的代码量对比

### 计数器（10 条事件后结束）

**case01 — 26 行**

```python
def sse_event(data: str, event: str | None = None, event_id: str | None = None, retry: int | None = None) -> str:
    parts = []
    if event_id: parts.append(f"id: {event_id}\n")
    if event:    parts.append(f"event: {event}\n")
    if retry is not None: parts.append(f"retry: {retry}\n")
    for line in data.split("\n"): parts.append(f"data: {line}\n")
    parts.append("\n")
    return "".join(parts)

@app.get("/sse/counter")
async def sse_counter(request: Request):
    async def generator():
        for i in range(1, 11):
            if await request.is_disconnected():
                break
            payload = json.dumps({"index": i, "ts": time.time()}, ensure_ascii=False)
            yield sse_event(data=payload, event="counter", event_id=str(i), retry=3000)
            await asyncio.sleep(1.0)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

**case02 — 16 行（少 ~40%）**

```python
@app.get("/sse/counter")
async def sse_counter(request: Request):
    async def generator():
        for i in range(1, 11):
            if await request.is_disconnected():
                break
            yield {
                "event": "counter",
                "id": str(i),
                "retry": 3000,
                "data": json.dumps({"index": i, "ts": time.time()}, ensure_ascii=False),
            }
            await asyncio.sleep(1.0)

    return EventSourceResponse(generator())
```

消失的样板代码：
- ❌ `sse_event(...)` 手动格式化函数（4 行）
- ❌ `media_type="text/event-stream"` 手动设
- ❌ `headers={...}` 手动设 3 个 header
- ❌ `\n\n` 拼写错的风险（库保证 100% 正确）

## 3. 核心差异逐条对照

| 维度 | case01 `StreamingResponse` | case02 `EventSourceResponse` |
|---|---|---|
| **数据格式** | 你 yield **字符串**（自己拼好 `data: ...\n\n`） | 你 yield **字典**（库自动格式化） |
| **必备 Header** | 手动设 `media_type` + 3 个 headers | ✅ **自动**（库内部加） |
| **心跳** | ❌ 自己写 `": heartbeat\n\n"` 或 yield 业务数据 | ✅ 构造时传 `ping=15`，库自动发 |
| **断线检测** | 手动 `await request.is_disconnected()` | 库内部 `listen_for_disconnect()`，自动取消 generator |
| **`X-Accel-Buffering: no`** | 手动加 | ✅ 自动加 |
| **`Last-Event-ID` 解析** | 手动 `request.headers.get(...)` | 仍然要手动（库不替你解析） |
| **多事件类型** | `event=...` 参数 | dict 的 `"event"` 键或 `ServerSentEvent` dataclass |
| **二进制数据** | 直接 yield bytes | `data_is_text=False` + dict 的 `"data"` 是 bytes |
| **底层** | Starlette 原生 `StreamingResponse` | **继承**自 `StreamingResponse`，外面包了 SSE 协议层 |
| **库依赖** | 无 | `sse-starlette`（已在项目 `uv.lock` 中） |

## 4. 心跳对比（最容易踩坑的点）

### case01 — 手动心跳

```python
async def generator():
    while True:
        if await request.is_disconnected():
            break

        # 业务数据
        yield sse_event(data=json.dumps({"ts": time.time()}), event="ping")

        # 心跳注释（手动）—— 客户端 EventSource 不触发事件，但能让代理保活
        yield sse_comment(f"keepalive {datetime.now()}")

        await asyncio.sleep(10.0)
```

如果忘了写 `sse_comment`，**60 秒后 Nginx/SLB 会主动掐断长连接**。

### case02 — 一行配置

```python
return EventSourceResponse(
    generator(),
    ping=15,  # ← 自动每 15 秒发 ": ping - <timestamp>\n\n"
)
```

库内部启动一个独立 asyncio 任务定期 yield 注释心跳，**永远不会忘**。

## 5. 实际运行效果（应看到）

```bash
# 启动两个 server
uvicorn example.sse.case01_streaming_response:app --port 8001 &
uvicorn example.sse.case02_event_source_response:app --port 8002 &

# case01: 计数器（10 条事件后结束）
curl -N http://localhost:8001/sse/counter

# case01: 长连接心跳（手动心跳注释）
curl -N http://localhost:8001/sse/heartbeat

# case02: 同样的计数器
curl -N http://localhost:8002/sse/counter

# case02: 长连接心跳（自动 ping=15）
curl -N http://localhost:8002/sse/heartbeat
```

**输出对比**（case01 vs case02 的 `/sse/heartbeat`）：

```text
# case01 - 手动心跳
event: ping
data: {"ts": "2026-09-11T14:55:00", "status": "alive"}

: keepalive 2026-09-11T14:55:00

[10 秒后]
event: ping
data: {"ts": "2026-09-11T14:55:10", "status": "alive"}

: keepalive 2026-09-11T14:55:10
...

# case02 - 自动 ping=15
event: ping
data: {"ts": "2026-09-11T14:55:00", "status": "alive"}

[15 秒后，无论 generator 是否 yield]
: ping - 2026-09-11T14:55:15

[10 秒后业务事件]
event: ping
data: {"ts": "2026-09-11T14:55:25", "status": "alive"}

: ping - 2026-09-11T14:55:30
```

可以看到 case02 即使业务事件 10 秒一次、心跳每 15 秒一次，**库会自动交替发送**，永远保持连接活跃。

## 6. 测试客户端

`test_client.py` 可以同时测两个 server，演示各种场景：

```bash
# 测试 case01 的计数器
python -m example.sse.test_client --server 8001 counter --max 5

# 测试 case02 的心跳
python -m example.sse.test_client --server 8002 heartbeat --max 3

# 演示 Last-Event-ID 断线恢复
python -m example.sse.test_client --server 8002 resume --resume
```

## 7. 何时选哪个？

| 场景 | 推荐 | 理由 |
|---|---|---|
| 标准 SSE，需要心跳 + 自动 header + 防 Nginx | ✅ **`EventSourceResponse`** | 少踩 5–8 行坑 |
| 不只是 SSE，还要支持 chunked transfer / NDJSON / protobuf | `StreamingResponse` | 更底层灵活 |
| 不依赖额外库 | `StreamingResponse` | 只需要 FastAPI |
| 已经在项目里跑得好好的 | 不用换 | 没坏就别修 |
| 需要发二进制 | 两者都行 | `EventSourceResponse` 要 `data_is_text=False` |

## 8. 给本项目 的建议

当前 `src/agent/app.py:201-225` 用的是 `StreamingResponse`，**运行良好，可以保持**。任务分钟级完成，事件间隔小于代理 60 秒超时，**目前不会出问题**。

但如果将来遇到以下情况，建议切换：

| 触发条件 | 切换动作 |
|---|---|
| 任务平均耗时 > 5 分钟 | 加 `sse_event(": heartbeat\n\n")` 心跳注释 |
| 部署到 Nginx + SLB 后面出现"长任务前端断流" | 切 `EventSourceResponse + ping=15` |
| 想精简 5–8 行样板代码 | 切 `EventSourceResponse` |
| 需要发二进制（如 PDF 流） | 用 `data_is_text=False` |

切换成本：< 5 行代码改动，且 `Last-Event-ID` 处理逻辑（`request.headers.get(...)`）保持不变。