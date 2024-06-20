import json
import time
import asyncio
import traceback
import bittensor as bt
from pydantic import BaseModel
from datetime import datetime
from typing import AsyncIterator, Optional, List, Union
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

    def ensure_response_is_created(
        self, initiated_response: web.StreamResponse
    ) -> web.StreamResponse:
        # Creates response if it was not created
        if initiated_response == None:
            initiated_response = web_response.StreamResponse(status=200, reason="OK")
            initiated_response.headers["Content-Type"] = "application/json"
            return initiated_response

        return initiated_response

    async def write_to_stream(
        self,
        request: web.Request,
        initiated_response: web.StreamResponse,
        stream_chunk: StreamChunk,
        lock: asyncio.Lock,
    ) -> web.StreamResponse:
        # Try to acquire the lock and sets the lock_acquired flag. Only the stream that acquires the lock should write to the response
        if lock.locked() == False:
            self.lock_acquired = await lock.acquire()

        if initiated_response == None and self.lock_acquired:
            initiated_response = self.ensure_response_is_created(initiated_response)
            # Prepare and send the headers
            await initiated_response.prepare(request)

        if self.lock_acquired:
            await initiated_response.write(stream_chunk.encode("utf-8"))
        else:
            bt.logging.debug(
                f"Stream of uid {stream_chunk.selected_uid} was not the first to return, skipping..."
            )

        return initiated_response

    async def stream(self, request: web.Request) -> ProcessedStreamResponse:
        # response = web_response.StreamResponse(status=200, reason="OK")
        # response.headers["Content-Type"] = "application/json"
        # await response.prepare(request)  # Prepare and send the headers

        try:
            start_time = time.time()
            client_response: web.Response = None
            final_response: ProcessedStreamResponse

            async for chunk in self.async_iterator:
                if isinstance(chunk, str):
                    # Chunks are currently returned in string arrays, so we need to concatenate them
                    concatenated_chunks = "".join(chunk)
                    self.accumulated_chunks.append(concatenated_chunks)
                    self.accumulated_chunks_timings.append(time.time() - start_time)
                    # Gets new response state
                    self.sequence_number += 1
                    new_response_state = self._create_chunk_response(
                        concatenated_chunks
                    )
                    # Writes the new response state to the response
                    client_response = await self.write_to_stream(
                        request, client_response, new_response_state, self.lock
                    )
                    # await response.write(new_response_state.encode('utf-8'))

            if chunk is not None and isinstance(chunk, StreamPromptingSynapse):
                if len(self.accumulated_chunks) == 0:
                    self.accumulated_chunks.append(chunk.completion)
                    self.accumulated_chunks_timings.append(time.time() - start_time)

                self.finish_reason = "completed"
                self.sequence_number += 1
                # Assuming the last chunk holds the last value yielded which should be a synapse with the completion filled
                synapse = chunk
                final_response = self._create_chunk_response(synapse.completion)

                if synapse.completion:
                    client_response = await self.write_to_stream(
                        request, client_response, final_response, self.lock
                    )
            else:
                raise ValueError("Stream did not return a valid synapse.")

        except Exception as e:
            bt.logging.error(
                f"Encountered an error while processing stream for uid {self.selected_uid} get_stream_response:\n{traceback.format_exc()}"
            )
            error_response = self._create_error_response(str(e))
            final_response = error_response

            # Only the stream that acquires the lock should write the error response
            if self.lock_acquired:
                self.ensure_response_is_created(client_response)
                client_response.set_status(500, reason="Internal error")
                client_response.write(error_response.encode("utf-8"))
        finally:
            # Only the stream that acquires the lock should close the response
            if self.lock_acquired:
                self.ensure_response_is_created(client_response)
                # Ensure to close the response properly
                await client_response.write_eof()

            return final_response

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
            selected_uid=self.selected_uid,
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
            sequence_number=self.sequence_number,
        )

    def _current_timestamp(self) -> str:
        """
        Returns the current timestamp in ISO format.

        :return: Current timestamp as a string.
        """
        return datetime.utcnow().isoformat()
