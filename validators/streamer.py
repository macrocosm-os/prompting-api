import json
import time
import traceback
import bittensor as bt
from pydantic import BaseModel
from datetime import datetime
from typing import AsyncIterator, Optional, List
from aiohttp import web, web_response
from prompting.protocol import StreamPromptingSynapse


class StreamChunk(BaseModel):
    delta: str
    finish_reason: Optional[str]
    accumulated_chunks: List[str]
    accumulated_chunks_timings: List[float]
    timestamp: str
    sequence_number: int
    selected_uid: int
    
    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)


class StreamError(BaseModel):
    error: str
    timestamp: str
    sequence_number: int
    finish_reason: str = 'error'

    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)


class AsyncResponseDataStreamer:
    def __init__(self, async_iterator: AsyncIterator, selected_uid:int, delay: float = 0.1):
        self.async_iterator = async_iterator        
        self.delay = delay
        self.selected_uid = selected_uid
        self.accumulated_chunks: List[str] = []
        self.accumulated_chunks_timings: List[float] = []
        self.finish_reason: str = None
        self.sequence_number: int = 0

    async def stream(self, request: web.Request) -> web_response.StreamResponse:    
        response = web_response.StreamResponse(status=200, reason="OK")
        response.headers["Content-Type"] = "application/json"
        await response.prepare(request)  # Prepare and send the headers
                        
        try:
            start_time = time.time()
            async for chunk in self.async_iterator:
                 if isinstance(chunk, list):
                    # Chunks are currently returned in string arrays, so we need to concatenate them
                    concatenated_chunks = "".join(chunk)
                    self.accumulated_chunks.append(concatenated_chunks)                    
                    self.accumulated_chunks_timings.append(time.time() - start_time)
                    # Gets new response state
                    self.sequence_number += 1
                    new_response_state = self._create_chunk_response(concatenated_chunks)                    
                    # Writes the new response state to the response                                    
                    await response.write(new_response_state.encode('utf-8'))
                                
            if chunk is not None and isinstance(chunk, StreamPromptingSynapse):                                                            
                self.finish_reason = "completed"
                self.sequence_number += 1
                # Assuming the last chunk holds the last value yielded which should be a synapse with the completion filled
                synapse = chunk 
                final_state = self._create_chunk_response(synapse.completion)
                await response.write(final_state.encode('utf-8'))
                                        
        except Exception as e:
            bt.logging.error(
                f"Encountered an error in {self.__class__.__name__}:get_stream_response:\n{traceback.format_exc()}"
            )
            response.set_status(500, reason="Internal error")
            error_response = self._create_error_response(str(e))
            response.write(error_response.encode('utf-8'))
        finally:
            await response.write_eof()  # Ensure to close the response properly
            return response

    def _create_chunk_response(self, chunk: str) -> StreamChunk:
        """
        Creates a StreamChunk object with the current state.

        :param chunk: List of strings representing the current chunk.
        :return: StreamChunk object.
        """
        return StreamChunk(
            delta=chunk,
            finish_reason=self.finish_reason,
            accumulated_chunks=self.accumulated_chunks,
            accumulated_chunks_timings=self.accumulated_chunks_timings,
            timestamp=self._current_timestamp(),
            sequence_number=self.sequence_number,
            selected_uid=self.selected_uid
        )

    def _create_error_response(self, error_message: str) -> StreamError:
        """
        Creates a StreamError object.

        :param error_message: Error message to include in the StreamError.
        :return: StreamError object.
        """
        return StreamError(
            error=error_message,
            timestamp=self._current_timestamp(),
            sequence_number=self.sequence_number
        )

    def _current_timestamp(self) -> str:
        """
        Returns the current timestamp in ISO format.

        :return: Current timestamp as a string.
        """
        return datetime.utcnow().isoformat()