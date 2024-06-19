import asyncio
from .streamer import AsyncResponseDataStreamer
from typing import List, AsyncIterator
from aiohttp.web import Request

class StreamManager:
    
    def __init__(self):
        ...
    
    
    
    async def process_streams(self, request:Request, streams_responses: List[AsyncIterator], stream_uids: List[int]):
        
        # create local lock for returning responses to the front-end
        # creates n number of streamers
        # organizes responses
        # logs responses locally
        # returns selected response to the front-end
        
        lock = asyncio.Lock()
        
        streamers = [AsyncResponseDataStreamer(async_iterator=stream, selected_uid=stream_uid, lock=lock) for stream, stream_uid in zip(streams_responses, stream_uids)]            
        completed_streams = await asyncio.gather(*[streamer.stream(request) for streamer in streamers])
        
        lock.release()
        print(f"Stream {stream_uids} completed the operation.")
        
                        



