import asyncio
from agent.task_queue import start_worker

if __name__ == "__main__":
    asyncio.run(start_worker())