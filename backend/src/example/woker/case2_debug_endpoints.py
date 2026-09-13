"""
case2_debug_endpoints.py
============================
直接在 PyCharm 里 Debug 整个 API 调用链 ——
不需要起 FastAPI，也不需要起前端/Redis HTTP 调用。

调用栈对应关系：
    ┌─ POST /api/research          →  enqueue_task()
    │   (src/agent/app.py:123)
    ├─ 后台 Worker 消费任务         →  start_worker() / _process_one_task()
    │   (src/agent/task_queue.py)
    └─ GET /api/research/{id}/stream → read_task_events()
        (src/agent/app.py:201)

使用方式：
    1. 在 PyCharm 中右键本文件 → "Debug 'case2_debug_endpoints'"
    2. 在以下位置打断点（任选）：
       - src/agent/app.py          submit_research()       —— 模拟 POST 入口
       - src/agent/task_queue.py   enqueue_task()           —— 入队 Redis Stream
       - src/agent/task_queue.py   _process_one_task()      —— Worker 消费
       - src/agent/task_queue.py   read_task_events()       —— SSE 事件流读取
       - src/agent/graph.py        generate_plan / evaluate_plan / confirm_plan
       - src/agent/sub_agents/*    子图节点
    3. Debug Console 会实时打印事件流（模拟 SSE 输出）
"""

import asyncio
import json
import sys
import pathlib

# ── 关键：把 src 加入 sys.path，让 agent.* 可被 import ─────────────
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR / "src"))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")  # 读取 backend/.env

from loguru import logger
from agent.task_queue import (
    enqueue_task,
    start_worker,
    read_task_events,
    TASK_STREAM,
)
from agent.logger import setup_logger

setup_logger()


# ════════════════════════════════════════════════════════════════════
# Step 1: 模拟 POST /api/research
# ════════════════════════════════════════════════════════════════════
async def simulate_post_research():
    """模拟 POST /api/research ——
    直接调用 app.py:123 submit_research 内部依赖的 enqueue_task。
    """
    print("\n" + "=" * 70)
    print("  [Step 1] 模拟 POST /api/research")
    print("=" * 70)

    # ── 入参（对应 app.py:138 解析后的 body）────────────────────
    body = {
        "messages": [
            {"type": "human", "content": "分析一下 2026 年 AI 芯片市场趋势"},
        ],
        "initial_search_query_count": 2,
        "max_research_loops": 2,
        "reasoning_model": "deepseek-v4-flash",
        "plan_status": "unconfirmed",   # 首次进入：触发 generate_plan
        "plan": "",
    }

    task_id = await enqueue_task(
        messages=body["messages"],
        initial_search_query_count=body["initial_search_query_count"],
        max_research_loops=body["max_research_loops"],
        reasoning_model=body["reasoning_model"],
        plan_status=body["plan_status"],
        plan=body["plan"],
        # task_id 不传 → 自动生成 UUID；想断点续传则固定传一个值
    )
    print(f"  → task_id 已下发: {task_id}")
    return task_id


# ════════════════════════════════════════════════════════════════════
# Step 2: 模拟后台 Worker（GET 请求触发的副作用）
# ════════════════════════════════════════════════════════════════════
async def simulate_worker(task_id: str):
    """模拟 start_worker 的核心循环 ——
    从 Redis Stream 消费一条任务 → 执行 graph → 把事件写回 event stream。
    """
    print("\n" + "=" * 70)
    print(f"  [Step 2] 模拟 Worker 消费 task_id={task_id[:8]}...")
    print("=" * 70)

    import redis.asyncio as redis
    from agent.task_queue import _process_one_task, _get_redis, _ensure_consumer_group

    r = await _get_redis()
    await _ensure_consumer_group(r)  # 确保 consumer group 存在

    # ── 给 Worker 设个超时，避免没任务时无限阻塞 ─────────────
    try:
        await asyncio.wait_for(_process_one_task(r), timeout=600)
        print(f"  → Worker 处理完毕")
    except asyncio.TimeoutError:
        print(f"  ⚠ Worker 超时（10 分钟）— 请检查 LLM 调用是否卡住")
    except Exception as exc:
        logger.exception(f"Worker 处理失败: {exc}")


# ════════════════════════════════════════════════════════════════════
# Step 3: 模拟 GET /api/research/{task_id}/stream  (SSE)
# ════════════════════════════════════════════════════════════════════
async def simulate_sse_stream(task_id: str, max_events: int = 200):
    """模拟 GET /api/research/{task_id}/stream ——
    调用 read_task_events 的内部 Generator，逐条打印事件。
    """
    print("\n" + "=" * 70)
    print(f"  [Step 3] 模拟 SSE 事件流读取")
    print("=" * 70)

    count = 0
    async for event_str in read_task_events(task_id, last_event_id="0"):
        count += 1
        # 模拟 SSE:  "data: <event>\n\n"
        print(f"\n  ┌─ event[{count}] ─────────────────────────────────")
        try:
            event = json.loads(event_str)
            print(f"  │  {json.dumps(event, ensure_ascii=False, indent=2)[:1500]}")
        except json.JSONDecodeError:
            print(f"  │  {event_str[:1500]}")

        # 检测终止事件
        try:
            event = json.loads(event_str)
            if any(k in event for k in ("finalize_answer", "error", "task_paused")):
                print(f"  └─ 终止事件 → SSE 连接关闭")
                break
        except json.JSONDecodeError:
            pass

        if count >= max_events:
            print(f"  └─ 达到 max_events={max_events}，提前断开")
            break


# ════════════════════════════════════════════════════════════════════
# 断点续传模式：模拟"用户在 Plan 确认处回车继续"
# ════════════════════════════════════════════════════════════════════
async def simulate_resume_after_plan_confirm(task_id: str, user_reply: str):
    """模拟第二次提交任务 —— 带上已确认的 plan，让图从 confirm_plan 继续。"""
    print("\n" + "=" * 70)
    print(f"  [Resume] 用户确认计划: \"{user_reply}\"")
    print("=" * 70)

    new_task_id = await enqueue_task(
        messages=[
            {"type": "human", "content": "分析一下 2026 年 AI 芯片市场趋势"},
            {"type": "ai", "content": "[上一次生成的计划内容...]"},
            {"type": "human", "content": user_reply},  # "开始研究" / "需求确认"
        ],
        initial_search_query_count=2,
        max_research_loops=2,
        reasoning_model="deepseek-v4-flash",
        plan_status="confirmed",   # ← 关键：跳过 generate_plan
        plan="[上一轮的计划 markdown 内容]",  # ← 复用
        task_id=task_id,           # ← 复用 thread_id，触发 checkpoint 续传
    )
    print(f"  → 续传 task_id={new_task_id}")
    return new_task_id


# ════════════════════════════════════════════════════════════════════
# Main — 串联三个阶段
# ════════════════════════════════════════════════════════════════════
async def main():
    print("\n🚀 DeepResearch 端到端 Case Debug\n")

    # ── 单次执行 ─────────────────────────────────────────────
    task_id = await simulate_post_research()
    worker_task = asyncio.create_task(simulate_worker(task_id))
    await asyncio.sleep(0.5)  # 给 worker 一点时间入队
    await simulate_sse_stream(task_id)
    await worker_task  # 确保 worker 也结束

    # ── 可选：断点续传演示（取消注释启用） ──────────────────
    # await simulate_resume_after_plan_confirm(task_id, "开始研究")
    # worker_task = asyncio.create_task(simulate_worker(task_id))
    # await asyncio.sleep(0.5)
    # await simulate_sse_stream(task_id)
    # await worker_task

    print("\n✅ Case 执行完成\n")


if __name__ == "__main__":
    asyncio.run(main())