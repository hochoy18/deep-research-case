# SSE (Server-Sent Events) Demo

## 文件说明

| 文件 | 作用 |
|------|------|
| `server.py` | FastAPI 服务端，提供 3 个 SSE 端点 |
| `client.html` | 浏览器端，用原生 `EventSource` + `fetch` 消费 |
| `client.py` | Python 端，用 `httpx` 流式消费 |

## 端点

- `GET /sse/{topic}` — 推送 10 条消息后自动结束，演示**有界流**
- `GET /heartbeat` — 无限循环推送心跳，演示**保活 / 长连接**
- `POST /chat` — 模拟 LLM token-by-token 流式输出，演示**语义事件名**

## 运行

```bash
uv add sse-starlette httpx
uvicorn example.sse.server:app --reload --port 8000

# 浏览器打开
open client.html

# 或 Python 客户端
python client.py
```

## SSE 协议要点

```
event: message          ← 事件名（默认 message）
id: 1                   ← 事件 ID，浏览器断线重连时会带上 Last-Event-ID
retry: 3000             ← 浏览器断线重连间隔（ms）
data: {"x": 1}          ← 负载（可多行，每行以 data: 开头）

                        ← 空行 = 一个事件结束
```

- `Content-Type: text/event-stream`
- 响应使用 chunked transfer，**不**带 `Content-Length`
- 每条事件以 `\n\n` 结束
- 注释行以 `:` 开头，可用于心跳
- 浏览器 `EventSource` 断线默认 3 秒自动重连

## 流程图

```
┌────────┐                              ┌────────┐
│ Browser│                              │ FastAPI│
│  (or   │                              │ Server │
│ client)│                              │        │
└───┬────┘                              └───┬────┘
    │ GET /sse/hello                       │
    │ Accept: text/event-stream            │
    │─────────────────────────────────────>│
    │                                       │
    │ HTTP/1.1 200                          │
    │ Content-Type: text/event-stream       │
    │ <─── stream chunked ────────────────│
    │                                       │
    │ data: {"index":1,...}\n\n             │  ← event 1
    │<──────────────────────────────────────│
    │ data: {"index":2,...}\n\n             │  ← event 2
    │<──────────────────────────────────────│
    │                  ... (持续推送)       │
    │                                       │
    │ [客户端断开 / 服务端结束]              │
    │<──────────────────────────────────────│
```

## 服务端实现关键

```python
async def event_generator():
    for i in range(10):
        yield {"event": "message", "id": str(i), "data": json.dumps({...})}
        await asyncio.sleep(1)

@app.get("/sse/{topic}")
async def sse_endpoint(request: Request):
    return EventSourceResponse(event_generator())
```

三件事必须做对：
1. **异步生成器** yield 事件 dict（`sse_starlette` 会负责序列化）
2. **检测客户端断开**：`await request.is_disconnected()`，避免无效推送
3. **不要在生成器里抛异常**，异常会导致连接提前关闭
