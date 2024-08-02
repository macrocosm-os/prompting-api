import asyncio
import datetime
import json
from collections import defaultdict
import time
import traceback
from typing import Any, AsyncIterator, Awaitable, Optional

import bittensor as bt
from aiohttp.web_response import StreamResponse
from aiohttp.web import Request
from prompting.protocol import StreamPromptingSynapse

from .stream_manager import StreamManager
from .streamer import StreamChunk


class ValidatorStreamManager(StreamManager):
    def __init__(self, chunks_to_wait: int = 1, miners_to_wait: int = 2):
        super().__init__()
        self._chosen_uid: Optional[int] = None
        self.client_response: Optional[StreamResponse] = None
        self._chunks_to_wait = chunks_to_wait
        self._miners_to_wait = miners_to_wait

    def _parse_stream(self, json_object: str, uid_to_chunks: dict[int, str]) -> list[Optional[dict[str, Any]]]:
        """Parse the JSON object and populate uid_to_chunks with the data."""
        if "}{" in json_object:
            # TODO: Investigate why some of the chunks may arrive in one sample.
            json_objects = json_object.split("}{")
            json_objects = [obj if obj.startswith("{") else "{" + obj for obj in json_objects]
            json_objects = [obj if obj.endswith("}") else obj + "}" for obj in json_objects]

            return [self.try_parse_json(obj, uid_to_chunks) for obj in json_objects]
        else:
            return [self.try_parse_json(json_object, uid_to_chunks)]

    def try_parse_json(self, json_object: str, uid_to_chunks: dict[int, str]) -> Optional[dict[str, Any]]:
        """Try to parse JSON and populate uid_to_chunks with the data."""
        try:
            data = json.loads(json_object)
            uid_to_chunks[data["uid"]].append(data["chunk"])
            return data
        except json.decoder.JSONDecodeError as e:
            bt.logging.error(f"An error occured when trying to parse JSON chunk: {e}")
        return None

    async def process_streams(
        self,
        request: Request,
        streams_responses: list[AsyncIterator],
        stream_uids: list[int],
    ) -> Optional[StreamResponse]:
        """Process multiple asynchronous streams, stream from first non-empty miner's chunk.

        Args:
            request (Request): The web request object.
            streams_responses (List[AsyncIterator]): A list of asynchronous iterators representing the streams.
            stream_uids (List[int]): A list of unique IDs for the streams.

        Returns:
            ProcessedStreamResponse: The response from the selected stream.
        """
        process_stream_tasks = [
            self._process_stream(request, uid, response)
            for uid, response in zip(stream_uids, streams_responses)
        ]

        processed_stream_results = await asyncio.gather(*process_stream_tasks, return_exceptions=True)
        return processed_stream_results[0]

    async def _stream_chunk(self, request: Request, response: StreamChunk):
        if self.client_response is None:
            self.client_response = StreamResponse(status=200, reason="OK")
            self.client_response.headers["Content-Type"] = "application/json"
            await self.client_response.prepare(request)

        bt.logging.info(f"Streaming: {response}")
        await self.client_response.write(response.encode("utf-8"))
        await self.client_response.drain()
    
    async def _stream_cached_responses(self, request: Request, responses: list[StreamChunk]):
        while len(responses) > 0:
            response = responses.pop(0)
            await self._stream_chunk(request, response)
            # TODO: Investigate why some of the chunks are concatenated when they streamed at the same time:
            # either front-end issue, or aiohttp.
            await asyncio.sleep(0.001)

    async def _process_stream(
        self,
        request: Request,
        uid: int,
        async_iterator: list[Awaitable],
    ) -> Optional[StreamResponse]:
        """Process a single response asynchronously."""
        synapse = None
        accumulated_chunks = defaultdict(list)
        accumulated_response_len = defaultdict(int)
        accumulated_chunks_timings = defaultdict(list)
        sequence_number = defaultdict(int)
        uid_to_chunks = defaultdict(list)
        responses = defaultdict(list)

        start_time = time.perf_counter()
        try:
            synapse = None
            async for chunk in async_iterator:
                if isinstance(chunk, str):
                    if not chunk:
                        continue

                    streams = self._parse_stream(chunk, uid_to_chunks)
                    # Take the longest completion first.
                    streams = sorted(streams, key=lambda x: len(x["chunk"]), reverse=True)
                    for data in streams:
                        miner_uid = data.get("uid")
                        response_chunk = data.get("chunk")

                        if self._chosen_uid is not None and miner_uid != self._chosen_uid:
                            # Miner UID is already chosen, skip the rest.
                            bt.logging.info(f"Skipping {miner_uid}, since Miner UID is chosen: {self._chosen_uid}")
                            continue

                        sequence_number[miner_uid] += 1
                        accumulated_chunks[miner_uid].append(response_chunk)
                        accumulated_response_len[miner_uid] += len(response_chunk)
                        accumulated_chunks_timings[miner_uid].append(time.perf_counter() - start_time)

                        response_state = StreamChunk(
                            delta=response_chunk,
                            finish_reason=None,
                            accumulated_chunks=accumulated_chunks[miner_uid],
                            accumulated_chunks_timings=accumulated_chunks_timings[miner_uid],
                            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            sequence_number=sequence_number[miner_uid],
                            selected_uid=miner_uid,
                        )
                        responses[miner_uid].append(response_state)
                        if (
                            len(responses[miner_uid]) >= self._chunks_to_wait
                            and accumulated_response_len[miner_uid] > 0
                            and len(responses) >= self._miners_to_wait
                        ):
                            if self._chosen_uid is None and miner_uid is not None:
                                # Choose current miner UID to stream.
                                self._chosen_uid = max(accumulated_response_len, key=accumulated_response_len.get)
                                bt.logging.info(f"Available responses len: {accumulated_response_len}")
                                bt.logging.info(f"Miner UID is chosen: {self._chosen_uid}")

                            # Stream chunks.
                            self._stream_cached_responses(request, responses[miner_uid])

                elif chunk is not None and isinstance(chunk, StreamPromptingSynapse):
                    if self._chosen_uid is None:
                        # If no UID met criteria, stream the longest completion.
                        self._chosen_uid = max(accumulated_response_len, key=accumulated_response_len.get)
                        bt.logging.info(f"Available responses len: {accumulated_response_len}")
                        bt.logging.info(f"Longest: {accumulated_response_len[self._chosen_uid]}. UID: {self._chosen_uid}")
                        # Stream chunks if they were not streamed during the processing loop.
                        self._stream_cached_responses(request, responses[self._chosen_uid])
                    synapse = chunk
                    if len(accumulated_chunks[self._chosen_uid]) == 0:
                        accumulated_chunks[self._chosen_uid].append(synapse.completion)
                        accumulated_chunks_timings[self._chosen_uid].append(time.perf_counter() - start_time)

                    # Stream completed.
                    final_response = StreamChunk(
                        delta="",
                        finish_reason="completed",
                        accumulated_chunks=accumulated_chunks[self._chosen_uid],
                        accumulated_chunks_timings=accumulated_chunks_timings[self._chosen_uid],
                        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        sequence_number=sequence_number[self._chosen_uid] + 1,
                        selected_uid=self._chosen_uid,
                    )

                    if synapse.completion:
                        await self._stream_chunk(request, final_response)
                else:
                    raise ValueError(f"Stream did not return a valid synapse, miner UID {miner_uid}")
        except Exception as e:
            traceback_details = traceback.format_exc()
            bt.logging.error(
                f"Error occuring during streaming responses for miner UID {miner_uid}: {e}\n{traceback_details}"
            )
        finally:
            if self.client_response is not None:
                await self.client_response.write_eof()  # Ensure the response is finalized
            return self.client_response
