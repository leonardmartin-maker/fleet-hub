import asyncio
from app.services.retry_queue import process_retry_queue


async def retry_worker():
    while True:
        await process_retry_queue()
        await asyncio.sleep(5)