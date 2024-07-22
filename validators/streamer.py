import json
import time
import asyncio
import traceback
from pydantic import BaseModel
from datetime import datetime
from typing import AsyncIterator, Optional, List, Union
from fastapi import Request
from prompting.protocol import StreamPromptingSynapse
from fastapi.responses import StreamingResponse
import bittensor as bt


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
    finish_reason: str = "error"

    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)


ProcessedStreamResponse = Union[StreamChunk, StreamError]


class AsyncResponseDataStreamer:
    def __init__(
        self,
        async_iterator: AsyncIterator,
        selected_uid: int,
        lock: asyncio.Lock,
        delay: float = 0.1,
    ):
        self.async_iterator = async_iterator
        self.delay = delay
        self.selected_uid = selected_uid
        self.accumulated_chunks: List[str] = []
        self.accumulated_chunks_timings: List[float] = []
        self.finish_reason: str = None
        self.sequence_number: int = 0
        self.lock = lock
        self.lock_acquired = False

    async def write_to_stream(
        self,
        response: StreamingResponse,
        stream_chunk: StreamChunk,
        lock: asyncio.Lock,
    ):
        if not lock.locked():
            self.lock_acquired = await lock.acquire()

        if self.lock_acquired:
            await response.write(stream_chunk.encode("utf-8"))
        else:
            bt.logging.debug(
                f"Stream of uid {stream_chunk.selected_uid} was not the first to return, skipping..."
            )

    async def stream(self, request: Request) -> ProcessedStreamResponse:
        try:
            start_time = time.time()
            response: StreamingResponse = StreamingResponse(
                self._stream_generator(request), media_type="application/json"
            )
            final_response: ProcessedStreamResponse

            async for chunk in self.async_iterator:
                if isinstance(chunk, str):
                    if not chunk:
                        continue

                    self.accumulated_chunks.append(chunk)
                    self.accumulated_chunks_timings.append(time.time() - start_time)
                    self.sequence_number += 1
                    new_response_state = self._create_chunk_response(chunk)
                    await self.write_to_stream(response, new_response_state, self.lock)

            if chunk is not None and isinstance(chunk, StreamPromptingSynapse):
                if len(self.accumulated_chunks) == 0:
                    self.accumulated_chunks.append(chunk.completion)
                    self.accumulated_chunks_timings.append(time.time() - start_time)

                self.finish_reason = "completed"
                self.sequence_number += 1
                synapse = chunk
                final_response = self._create_chunk_response(synapse.completion)

                if synapse.completion:
                    await self.write_to_stream(response, final_response, self.lock)
            else:
                raise ValueError("Stream did not return a valid synapse.")

        except Exception as e:
            bt.logging.error(
                f"Encountered an error while processing stream for uid {self.selected_uid} get_stream_response:\n{traceback.format_exc()}"
            )
            error_response = self._create_error_response(str(e))
            final_response = error_response

            if self.lock_acquired:
                await response.write(error_response.encode("utf-8"))
        finally:
            if self.lock_acquired:
                await response.close()

            return final_response

    async def _stream_generator(self, request: Request):
        async for chunk in self.async_iterator:
            yield chunk.encode("utf-8")
            await asyncio.sleep(self.delay)

    def _create_chunk_response(self, chunk: str) -> StreamChunk:
        return StreamChunk(
            delta=chunk,
            finish_reason=self.finish_reason,
            accumulated_chunks=self.accumulated_chunks,
            accumulated_chunks_timings=self.accumulated_chunks_timings,
            timestamp=self._current_timestamp(),
            sequence_number=self.sequence_number,
            selected_uid=self.selected_uid,
        )

    def _create_error_response(self, error_message: str) -> StreamError:
        return StreamError(
            error=error_message,
            timestamp=self._current_timestamp(),
            sequence_number=self.sequence_number,
        )

    def _current_timestamp(self) -> str:
        return datetime.utcnow().isoformat()
