"""
SSE 测试客户端 —— 同时测两个 case
==================================

使用方法：
    # 先启动两个 server（不同端口）
    uvicorn example.sse.case01_streaming_response:app --port 8001 &
    uvicorn example.sse.case02_event_source_response:app --port 8002 &

    # 然后跑测试
    python -m example.sse.test_client --server 8001 counter
    python -m example.sse.test_client --server 8002 heartbeat
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx


async def consume_sse(url: str, max_events: int = 5) -> None:
    """消费 SSE 流，打印事件."""
    print(f"[client] GET {url}\n")

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as resp:
            print(f"[status] {resp.status_code}, content-type={resp.headers.get('content-type')}")
            print(f"[headers] cache-control={resp.headers.get('cache-control')}, "
                  f"x-accel-buffering={resp.headers.get('x-accel-buffering')}")
            print("-" * 60)

            event_type = "message"
            event_id: str | None = None
            data_lines: list[str] = []
            count = 0

            async for line in resp.aiter_lines():
                # 空行 = 一个事件结束
                if line == "":
                    if data_lines:
                        data_str = "\n".join(data_lines)
                        try:
                            data_obj = json.loads(data_str)
                            data_repr = json.dumps(data_obj, ensure_ascii=False)
                        except (json.JSONDecodeError, TypeError):
                            data_repr = data_str
                        print(f"[event={event_type:<10}] id={event_id} data={data_repr}")
                        event_type = "message"
                        event_id = None
                        data_lines = []
                        count += 1
                        if count >= max_events:
                            print(f"\n[client] 已收到 {count} 条事件，主动断开")
                            return
                    continue

                # 注释行
                if line.startswith(":"):
                    print(f"[comment] {line[1:].strip()}")
                    continue

                field, _, value = line.partition(":")
                value = value.lstrip()
                if field == "event":
                    event_type = value
                elif field == "data":
                    data_lines.append(value)
                elif field == "id":
                    event_id = value
                elif field == "retry":
                    print(f"[retry] {value} ms")


async def test_last_event_id(url: str) -> None:
    """演示 Last-Event-ID 断线恢复."""
    print(f"[client] 先订阅 {url}，拿 Last-Event-ID")
    print("-" * 60)

    last_id = "0"

    async with httpx.AsyncClient(timeout=None) as client:
        # 第一段：只拿前 3 个事件就断开
        async with client.stream(
            "GET", url, headers={"Last-Event-ID": last_id}
        ) as resp:
            count = 0
            async for line in resp.aiter_lines():
                if line.startswith("id:"):
                    last_id = line.partition(":")[2].strip()
                if line == "":
                    count += 1
                    if count >= 3:
                        print(f"\n[client] 已收到 {count} 个事件，最后 id={last_id}，模拟断线\n")
                        break
                # 用完 3 个事件就关闭响应

        # 第二段：带 Last-Event-ID 重连
        print(f"[client] 重连，带 Last-Event-ID: {last_id}")
        print("-" * 60)
        async with client.stream(
            "GET", url, headers={"Last-Event-ID": last_id}
        ) as resp:
            count = 0
            async for line in resp.aiter_lines():
                if line == "":
                    count += 1
                    if count >= 3:
                        break
                print(line)
            print(f"\n[client] 重连后再收 {count} 个事件 → 验证从 {last_id} 之后续推")


async def main() -> None:
    parser = argparse.ArgumentParser(description="SSE 测试客户端")
    parser.add_argument(
        "--server",
        type=int,
        default=8002,
        help="server 端口：8001 = case01（StreamingResponse）, 8002 = case02（EventSourceResponse）",
    )
    parser.add_argument(
        "endpoint",
        nargs="?",
        default="counter",
        choices=["counter", "token", "events", "heartbeat", "resume", "structured"],
        help="要测试的端点",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=5,
        help="最多接收多少条事件后断开（heartbeat 默认会一直收）",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="演示 Last-Event-ID 断线恢复",
    )

    args = parser.parse_args()
    url = f"http://localhost:{args.server}/sse/{args.endpoint}"

    if args.resume or args.endpoint == "resume":
        await test_last_event_id(url)
    else:
        await consume_sse(url, max_events=args.max)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[client] 用户中断")
        sys.exit(0)