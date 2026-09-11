"""
SSE (Server-Sent Events) FastAPI 实现
=====================================

SSE 流程：
  1. 客户端通过 EventSource（或 HTTP GET）发起请求，声明 Accept: text/event-stream
  2. 服务端保持连接不断开，返回 text/event-stream 响应
  3. 服务端按 SSE 协议格式（data: ...\\n\\n）持续推送事件
  4. 客户端自动接收并通过 onmessage / onevent 回调处理
  5. 连接断开时，客户端可自动重连（Last-Event-ID 续传）

运行：
  uv run python -m example.sse.server
  或
  uvicorn example.sse.server:app --reload
"""
import asyncio
import json
import time
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="SSE Demo")


async def event_generator(request: Request, topic: str):
    """事件生成器：持续产出 SSE 事件，直到客户端断开。"""
    last_id = request.headers.get("last-event-id") or "0"
    start = int(last_id) + 1
    for i in range(start, start + 20):
        if await request.is_disconnected():
            break
        payload = {"topic": topic, "index": i, "ts": time.time(), "resumed_from": last_id}
        yield {
            "event": "message",
            "id": str(i),
            "retry": 3000,
            "data": json.dumps(payload, ensure_ascii=False),
        }
        await asyncio.sleep(0.3)


@app.get("/sse/{topic}")
async def sse_endpoint(topic: str, request: Request):
    """SSE 端点：返回 StreamingResponse，Content-Type 固定为 text/event-stream。"""
    return EventSourceResponse(event_generator(request, topic))


@app.post("/chat")
async def chat(request: Request):
    """模拟 LLM 流式输出：每次 yield 一个 token，客户端逐字接收。"""
    body = await request.json()
    prompt = body.get("prompt", "")

    async def token_stream():
        reply = f"你问的是：{prompt}。这是一个 SSE 流式响应示例。"
        for token in reply.split():
            yield {"event": "token", "data": token}
            await asyncio.sleep(0.2)
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(token_stream())


@app.get("/heartbeat")
async def heartbeat(request: Request):
    """心跳示例：保持连接 + 周期性推送，演示如何保活。"""
    async def stream():
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "ping", "data": json.dumps({"ts": time.time()})}
            await asyncio.sleep(5)

    return EventSourceResponse(stream())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
