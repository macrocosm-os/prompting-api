import asyncio
import bittensor as bt
from .streamer import AsyncResponseDataStreamer
from .database import LogDatabase
from typing import List, AsyncIterator
from aiohttp.web import Request


class StreamManager:
    def __init__(self, log_database_path: str = "requests_db.jsonl"):
        self.log_database = LogDatabase(log_database_path)
    
    async def process_streams(self, request:Request, streams_responses: List[AsyncIterator], stream_uids: List[int]):
        lock = asyncio.Lock()
        
        streamers = [AsyncResponseDataStreamer(async_iterator=stream, selected_uid=stream_uid, lock=lock) for stream, stream_uid in zip(streams_responses, stream_uids)]            
        completed_streams = await asyncio.gather(*[streamer.stream(request) for streamer in streamers])
        
        lock.release()
        bt.logging.info(f"Streams from uids: {stream_uids} processing completed.")
        

        await self.log_database.add_streams_to_db(completed_streams)
        # Gets the first stream that acquired the lock, meaning the first stream that was able to return a non-empty chunk
        _, selected_stream = next(((streamer, completed_stream) for streamer, completed_stream in zip(streamers, completed_streams) if streamer.lock_acquired), None)
        
        return selected_stream 
        
