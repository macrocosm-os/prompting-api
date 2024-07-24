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
    def __init__(self):
        super().__init__()
        self._chosen_uid: Optional[int] = None

    def _parse_stream(self, json_object: str, uid_to_chunks: dict[int, str]) -> list[Optional[dict[str, Any]]]:
        if "}{" in json_object:
            # If multiple chunks arrived in one sample.
            json_objects = json_object.split("}{")
            json_objects = [obj if obj.startswith("{") else "{" + obj for obj in json_objects]
            json_objects = [obj if obj.endswith("}") else obj + "}" for obj in json_objects]

            # Parse each JSON object.
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

    async def _process_stream(
        self,
        request: Request,
        uid: int,
        async_iterator: list[Awaitable],
    ) -> Optional[StreamResponse]:
        """Process a single response asynchronously."""
        synapse = None
        accumulated_chunks = defaultdict(list)
        accumulated_chunks_timings = defaultdict(list)
        sequence_number = defaultdict(int)
        uid_to_chunks = defaultdict(list)
        client_response: Optional[StreamResponse] = None

        start_time = time.perf_counter()
        try:
            synapse = None
            async for chunk in async_iterator:
                if isinstance(chunk, str):
                    if not chunk:
                        continue

                    streams = self._parse_stream(chunk, uid_to_chunks)
                    # Take the longest completion first.
                    streams = sorted(streams, key=lambda x: len(x['chunk']), reverse=True)
                    for data in streams:
                        miner_uid = data.get("uid")
                        response_chunk = data.get("chunk")
                        if self._chosen_uid is not None and miner_uid != self._chosen_uid:
                            continue

                        if self._chosen_uid is None and miner_uid is not None and response_chunk is not None:
                            self._chosen_uid = miner_uid

                        sequence_number[miner_uid] += 1
                        accumulated_chunks[miner_uid].append(response_chunk)
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

                        if client_response is None:
                            client_response = StreamResponse(status=200, reason="OK")
                            client_response.headers["Content-Type"] = "application/json"
                            await client_response.prepare(request)
                        await client_response.write(response_state.encode("utf-8"))
                elif chunk is not None and isinstance(chunk, StreamPromptingSynapse):
                    if self._chosen_uid is None:
                        continue
                    synapse = chunk
                    if len(accumulated_chunks[self._chosen_uid]) == 0:
                        accumulated_chunks[self._chosen_uid].append(synapse.completion)
                        accumulated_chunks_timings[self._chosen_uid].append(time.perf_counter() - start_time)

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
                        await client_response.write(final_response.encode("utf-8"))
                else:
                    raise ValueError(f"Stream did not return a valid synapse, miner UID {miner_uid}")
        except Exception as e:
            traceback_details = traceback.format_exc()
            bt.logging.error(
                f"Error occuring during streaming responses for miner UID {miner_uid}: {e}\n{traceback_details}"
            )
        finally:
            return client_response
