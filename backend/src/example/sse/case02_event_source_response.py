"""
SSE Case 02: sse-starlette EventSourceResponse 实现
===================================================

目标：用 sse-starlette 的 EventSourceResponse 实现与 case01 完全一样的 5 个 SSE 端点。
对比 case01_streaming_response.py 看哪些样板代码消失了。

运行：
    uv run python -m example.sse.case02_event_source_response
    或
    uvicorn example.sse.case02_event_source_response:app --port 8002 --reload

测试：
    curl -N http://localhost:8002/sse/counter
    curl -N http://localhost:8002/sse/token
    curl -N http://localhost:8002/sse/events
    curl -N http://localhost:8002/sse/heartbeat
    curl -N http://localhost:8002/sse/resume

依赖（已在 backend/uv.lock 中）：
    sse-starlette>=3.0
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import AsyncIterator

from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

app = FastAPI(title="SSE Case 02 - EventSourceResponse", version="1.0")


# ──────────────────────────────────────────────────────────────────
# 端点 1: /sse/counter —— 有界流
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/counter")
async def sse_counter(request: Request):
    """10 个事件后自动结束.

    与 case01 对比：
      - 不再自己写 "data: ...\\n\\n"
      - 不再手动设 headers（库自动加 text/event-stream / no-cache / X-Accel-Buffering: no）
      - 直接 yield dict，库自动序列化
    """
    async def generator() -> AsyncIterator[dict]:
        for i in range(1, 11):
            # 客户端断开检测（库内部其实也会处理 CancelledError）
            if await request.is_disconnected():
                break

            yield {
                "event": "counter",
                "id": str(i),
                "retry": 3000,
                "data": json.dumps(
                    {"index": i, "ts": time.time()},
                    ensure_ascii=False,
                ),
            }
            await asyncio.sleep(1.0)

    return EventSourceResponse(generator())


# ──────────────────────────────────────────────────────────────────
# 端点 2: /sse/token —— 模拟 LLM token 流式输出
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/token")
async def sse_token(request: Request):
    """逐 token 输出."""

    async def generator() -> AsyncIterator[dict]:
        reply = "你 好 ，这 是 SSE 流 式 响 应 演 示"
        for idx, token in enumerate(reply.split()):
            if await request.is_disconnected():
                break
            yield {
                "event": "token",
                "id": str(idx),
                "data": json.dumps({"text": token}, ensure_ascii=False),
            }
            await asyncio.sleep(0.2)

        yield {
            "event": "done",
            "data": json.dumps({"reason": "completed"}, ensure_ascii=False),
        }

    return EventSourceResponse(generator())


# ──────────────────────────────────────────────────────────────────
# 端点 3: /sse/events —— 多事件类型演示
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/events")
async def sse_events(request: Request):
    """演示 event 字段如何区分不同类型的事件."""

    async def generator() -> AsyncIterator[dict]:
        yield {"event": "start",    "id": "1", "data": json.dumps({"stage": "start"},    ensure_ascii=False)}
        await asyncio.sleep(0.5)

        for i in range(1, 6):
            if await request.is_disconnected():
                break
            yield {
                "event": "progress",
                "id": str(1 + i),
                "data": json.dumps({"percent": i * 20}, ensure_ascii=False),
            }
            await asyncio.sleep(0.5)

        yield {
            "event": "result",
            "id": "7",
            "data": json.dumps(
                {"answer": "分析完成：AI 芯片市场规模 800 亿美元"},
                ensure_ascii=False,
            ),
        }
        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(generator())


# ──────────────────────────────────────────────────────────────────
# 端点 4: /sse/heartbeat —— 长连接 + 内置心跳
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/heartbeat")
async def sse_heartbeat(request: Request):
    """长连接 + 内置 ping 心跳.

    与 case01 最大的区别：
      - case01 必须手写 ": heartbeat\\n\\n" 注释心跳
      - case02 只需在构造时传 ping=15，库会自动定期发送
    """
    async def generator() -> AsyncIterator[dict]:
        while True:
            if await request.is_disconnected():
                break
            now = datetime.now().isoformat(timespec="seconds")
            yield {
                "event": "ping",
                "data": json.dumps({"ts": now, "status": "alive"}, ensure_ascii=False),
            }
            await asyncio.sleep(10.0)

    return EventSourceResponse(
        generator(),
        ping=15,  # ← 自动每 15 秒发 ": ping - <timestamp>\\n\\n" 心跳
    )


# ──────────────────────────────────────────────────────────────────
# 端点 5: /sse/resume —— Last-Event-ID 断线恢复
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/resume")
async def sse_resume(request: Request):
    """演示 Last-Event-ID 机制.

    注意：EventSourceResponse 不会自动读取 Last-Event-ID 并传给 generator，
    仍然需要从 request.headers 自己取（与 case01 一致）。
    """
    last_event_id = request.headers.get("last-event-id", "0")
    start = int(last_event_id) + 1

    async def generator() -> AsyncIterator[dict]:
        for i in range(start, start + 10):
            if await request.is_disconnected():
                break
            yield {
                "event": "message",
                "id": str(i),
                "data": json.dumps(
                    {"index": i, "resumed_from": last_event_id},
                    ensure_ascii=False,
                ),
            }
            await asyncio.sleep(0.5)

    return EventSourceResponse(generator())


# ──────────────────────────────────────────────────────────────────
# 端点 6: /sse/structured —— 用 ServerSentEvent dataclass
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/structured")
async def sse_structured(request: Request):
    """用 ServerSentEvent dataclass 显式构造事件.

    适合复杂场景：需要字段校验 / 类型提示 / 默认值。
    """
    async def generator() -> AsyncIterator[ServerSentEvent]:
        yield ServerSentEvent(
            event="start",
            id="1",
            data=json.dumps({"stage": "start"}, ensure_ascii=False),
        )
        await asyncio.sleep(0.5)

        for i in range(1, 4):
            if await request.is_disconnected():
                break
            yield ServerSentEvent(
                event="progress",
                id=str(1 + i),
                data=json.dumps({"percent": i * 33}, ensure_ascii=False),
            )
            await asyncio.sleep(0.5)

        yield ServerSentEvent(
            event="done",
            data="[DONE]",
        )

    return EventSourceResponse(generator(), ping=10)


# ──────────────────────────────────────────────────────────────────
# 端点 7: /sse/binary —— 二进制数据演示
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/binary")
async def sse_binary(request: Request):
    """演示 SSE 发送二进制数据.

    EventSourceResponse 默认 data 是文本，要发二进制需要 data_is_text=False。
    注意：浏览器原生 EventSource 不支持二进制，需要用 fetch + ReadableStream。
    """
    async def generator() -> AsyncIterator[dict]:
        for i in range(5):
            if await request.is_disconnected():
                break
            # 二进制内容（4 字节整数）
            yield {"event": "bytes", "data": i.to_bytes(4, "big")}
            await asyncio.sleep(0.5)

    return EventSourceResponse(generator(), data_is_text=False)


# ──────────────────────────────────────────────────────────────────
# 启动入口
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("SSE Case 02 — EventSourceResponse（库封装）")
    print("=" * 60)
    print("端点：")
    print("  GET /sse/counter      — 10 个事件后结束")
    print("  GET /sse/token        — 模拟 LLM token 流")
    print("  GET /sse/events       — 多事件类型")
    print("  GET /sse/heartbeat    — 长连接 + ping=15 自动心跳")
    print("  GET /sse/resume       — Last-Event-ID 断线恢复")
    print("  GET /sse/structured   — ServerSentEvent dataclass")
    print("  GET /sse/binary       — 二进制数据")
    print("测试：")
    print("  curl -N http://localhost:8002/sse/counter")
    print("  curl -N http://localhost:8002/sse/heartbeat")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8002)