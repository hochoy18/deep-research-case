"""
SSE Case 01: FastAPI 原生 StreamingResponse 实现
=================================================

目标：用最底层的 Starlette/FastAPI 原语手写一个 SSE 端点。
所有 SSE 协议细节都自己处理（data: ...\\n\\n、headers、心跳、Last-Event-ID）。

运行：
    uv run python -m example.sse.case01_streaming_response
    或
    uvicorn example.sse.case01_streaming_response:app --port 8001 --reload

测试：
    curl -N http://localhost:8001/sse/counter
    curl -N http://localhost:8001/sse/token
    curl -N http://localhost:8001/sse/events
    curl -N http://localhost:8001/sse/heartbeat

注意：本文件不依赖 sse-starlette，是 FastAPI 自带的 StreamingResponse。
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="SSE Case 01 - StreamingResponse", version="1.0")

# ──────────────────────────────────────────────────────────────────
# 辅助：手动构造 SSE 帧
# ──────────────────────────────────────────────────────────────────
# SSE 协议规定每个事件由若干 "field: value" 行 + 一个空行组成：
#   event: message
#   id: 100
#   data: {"x": 1}
#   \n  ← 空行 = 一个事件结束
#
# 写错 \\n\\n 是 SSE 最大的坑，本文件所有 yield 都走下面的 helper，
# 确保格式 100% 正确（每条事件都以 \\n\\n 结束）。

def sse_event(
    data: str,
    event: str | None = None,
    event_id: str | None = None,
    retry: int | None = None,
) -> str:
    """构造一条 SSE 事件（已包含结尾的 \\n\\n）."""
    parts: list[str] = []
    if event_id:
        parts.append(f"id: {event_id}\n")
    if event:
        parts.append(f"event: {event}\n")
    if retry is not None:
        parts.append(f"retry: {retry}\n")
    # data 可能含换行，需要拆成多行 data: 字段
    for line in data.split("\n"):
        parts.append(f"data: {line}\n")
    parts.append("\n")  # ← 空行表示事件结束
    return "".join(parts)


def sse_comment(text: str) -> str:
    """SSE 注释行：以 ':' 开头，客户端不触发事件。常用于心跳。"""
    return f": {text}\n\n"


# ──────────────────────────────────────────────────────────────────
# 端点 1: /sse/counter —— 有界流（10 条后结束）
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/counter")
async def sse_counter(request: Request):
    """每 1 秒推一个数字，10 个后自动结束.

    演示要点：
      - data: ...\\n\\n 手动构造
      - 必备的 SSE headers 手动设置
      - 用 request.is_disconnected() 客户端断开检测
    """
    async def generator() -> AsyncIterator[str]:
        try:
            for i in range(1, 11):
                # 客户端断开 → 立即停止推送
                if await request.is_disconnected():
                    break

                payload = json.dumps(
                    {"index": i, "ts": time.time()},
                    ensure_ascii=False,
                )
                yield sse_event(
                    data=payload,
                    event="counter",
                    event_id=str(i),
                    retry=3000,  # 告诉浏览器断线后 3 秒重连
                )
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            # 客户端断网时，FastAPI 会取消 generator
            print("[counter] 客户端断开，generator 被取消")
            raise

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",  # ← 必须
        headers={
            "Cache-Control": "no-cache",   # ← 必须
            "Connection": "keep-alive",    # ← 必须
            "X-Accel-Buffering": "no",     # ← 关掉 Nginx 缓冲（重点）
        },
    )


# ──────────────────────────────────────────────────────────────────
# 端点 2: /sse/token —— 模拟 LLM token 流式输出
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/token")
async def sse_token(request: Request):
    """模拟 LLM 逐 token 输出：每个字/词一个事件.

    演示要点：
      - 自定义 event 名（区别于默认 message）
      - 每次 yield 一个事件，浏览器端能实时渲染打字机效果
    """
    async def generator() -> AsyncIterator[str]:
        reply = "你 好 ，这 是 SSE 流 式 响 应 演 示"
        # 也可改成按字符："你好，这是 SSE 流式响应演示"

        try:
            for idx, token in enumerate(reply.split()):
                if await request.is_disconnected():
                    break

                # 每个 token 一个事件，data 字段是 JSON
                yield sse_event(
                    data=json.dumps({"text": token}, ensure_ascii=False),
                    event="token",
                    event_id=str(idx),
                )
                await asyncio.sleep(0.2)

            # 最后一条 done 事件
            yield sse_event(
                data=json.dumps({"reason": "completed"}, ensure_ascii=False),
                event="done",
            )
        except asyncio.CancelledError:
            print("[token] 客户端断开，generator 被取消")
            raise

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────
# 端点 3: /sse/events —— 多事件类型演示
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/events")
async def sse_events(request: Request):
    """演示 event 字段如何区分不同类型的事件.

    客户端可以用 addEventListener("progress", handler) 单独订阅。
    """
    async def generator() -> AsyncIterator[str]:
        try:
            # ① start
            yield sse_event(
                data=json.dumps({"stage": "start"}, ensure_ascii=False),
                event="start",
                event_id="1",
            )
            await asyncio.sleep(0.5)

            # ② progress × 5
            for i in range(1, 6):
                if await request.is_disconnected():
                    break
                yield sse_event(
                    data=json.dumps({"percent": i * 20}, ensure_ascii=False),
                    event="progress",
                    event_id=str(1 + i),
                )
                await asyncio.sleep(0.5)

            # ③ result
            yield sse_event(
                data=json.dumps(
                    {"answer": "分析完成：AI 芯片市场规模 800 亿美元"},
                    ensure_ascii=False,
                ),
                event="result",
                event_id="7",
            )

            # ④ done
            yield sse_event(
                data="[DONE]",
                event="done",
            )
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────
# 端点 4: /sse/heartbeat —— 长连接 + 心跳保活
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/heartbeat")
async def sse_heartbeat(request: Request):
    """长连接 + 手动心跳.

    演示要点：
      - 60 秒没数据 → Nginx / 阿里云 SLB 会主动断开连接
      - 必须定期发 ": heartbeat\\n\\n" 注释行保活
      - 本端点每 10 秒发一次心跳，演示纯手工心跳写法
    """
    async def generator() -> AsyncIterator[str]:
        try:
            while True:
                if await request.is_disconnected():
                    break

                now = datetime.now().isoformat(timespec="seconds")

                # 业务数据（每 10 秒）
                yield sse_event(
                    data=json.dumps({"ts": now, "status": "alive"}, ensure_ascii=False),
                    event="ping",
                )

                # 心跳注释（客户端 EventSource 不会触发事件，
                # 但能让代理服务器知道连接还活着）
                # 注意：这里业务 yield 已经能保活，
                # 演示中再加一条注释心跳显得更稳。
                yield sse_comment(f"keepalive {now}")

                await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            print("[heartbeat] 客户端断开，generator 被取消")
            raise

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────
# 端点 5: /sse/resume —— Last-Event-ID 断线恢复
# ──────────────────────────────────────────────────────────────────
@app.get("/sse/resume")
async def sse_resume(request: Request):
    """演示 Last-Event-ID 机制：客户端重连时带上最后收到的事件 ID.

    浏览器原生 EventSource 会自动做这件事（断网后带 Last-Event-ID 重连）。
    curl / Python httpx 也支持手动指定。
    """
    last_event_id = request.headers.get("last-event-id", "0")
    start = int(last_event_id) + 1

    async def generator() -> AsyncIterator[str]:
        try:
            for i in range(start, start + 10):
                if await request.is_disconnected():
                    break
                yield sse_event(
                    data=json.dumps(
                        {"index": i, "resumed_from": last_event_id},
                        ensure_ascii=False,
                    ),
                    event="message",
                    event_id=str(i),
                )
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────
# 启动入口
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("SSE Case 01 — StreamingResponse（手工实现）")
    print("=" * 60)
    print("端点：")
    print("  GET /sse/counter    — 10 个事件后结束")
    print("  GET /sse/token      — 模拟 LLM token 流")
    print("  GET /sse/events     — 多事件类型")
    print("  GET /sse/heartbeat  — 长连接 + 心跳")
    print("  GET /sse/resume     — Last-Event-ID 断线恢复")
    print("测试：")
    print("  curl -N http://localhost:8001/sse/counter")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8001)