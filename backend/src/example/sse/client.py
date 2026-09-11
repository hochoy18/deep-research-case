"""
Python SSE 客户端：用 httpx 流式请求，解析 data: ...\\n\\n 协议格式。
"""
import asyncio
import httpx


async def main():
    url = "http://localhost:8000/sse/hello-good-for-you"
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as resp:
            print(f"[status] {resp.status_code}, content-type={resp.headers.get('content-type')}")

            event_type, data_lines = "message", []
            async for line in resp.aiter_lines():
                if line == "":
                    if data_lines:
                        print(f"[{event_type}] {''.join(data_lines)}")
                        event_type, data_lines = "message", []
                    continue
                if line.startswith(":"):
                    continue
                field, _, value = line.partition(":")
                value = value.lstrip()
                if field == "event":
                    event_type = value
                elif field == "data":
                    data_lines.append(value)
                elif field == "id":
                    print(f"  last-event-id={value}")


if __name__ == "__main__":
    asyncio.run(main())
