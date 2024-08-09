import asyncio
import async_timeout
import datetime
import json
from collections import defaultdict
import time
import traceback
from typing import Any, AsyncIterator, Awaitable, List, Optional

import bittensor as bt
from fastapi.responses import StreamingResponse
from fastapi import Request, HTTPException

from common.schemas import QueryChatRequest
from .protocol import StreamPromptingSynapse
from .stream_utils import StreamChunk

from loguru import logger


class StreamManager:
    def __init__(self, request: QueryChatRequest):
        super().__init__()
        self.selected_miners: set[int] = set()
        self.request = request
        self.client_response_chunks: list[StreamChunk] = []

    async def stream_generator(
        self,
        streams_responses: list[AsyncIterator],
        stream_uids: Optional[list[int]],
        query_validators: bool,
    ) -> AsyncIterator:

        self.accumulated_chunks = defaultdict(list)
        self.accumulated_timings = defaultdict(list)
        self.start_time = time.perf_counter()

        try:
            async with async_timeout.timeout(self.request.timeout):
                for stream_response, uid in zip(streams_responses, stream_uids):
                    # Determine which UID was passed in
                    validator_uid = uid if query_validators else -1
                    miner_uid = uid if not query_validators else -1
                    logger.info(f"Miner UID: {miner_uid}, Validator UID: {validator_uid}")

                    async for raw_chunk in stream_response:
                        if isinstance(raw_chunk, str):
                            for chunk in self.split_chunks(raw_chunk):
                                processed_chunk = self.process_chunk(chunk, miner_uid, validator_uid)
                                if processed_chunk is None:
                                    continue
                                yield processed_chunk
                        elif isinstance(raw_chunk, StreamPromptingSynapse):
                            # This is the last chunk of the stream
                            last_chunk = self.process_last_chunk("completed", miner_uid, validator_uid)
                            yield last_chunk
                        else:
                            raise ValueError(f"Stream did not return a valid synapse, chunk: {raw_chunk}")
        except asyncio.TimeoutError:
            logger.error(f"Stream timed out after {self.request.timeout} seconds")
            last_chunk = self.process_last_chunk("timed out", miner_uid, validator_uid)
            yield last_chunk

    def split_chunks(self, raw_chunk: str) -> list[str]:
        delm = ">>|break|<<"
        return raw_chunk.replace("}{", "}" + delm + "{").split(delm)

    def process_chunk(self, chunk: str, miner_uid: int, validator_uid: int) -> Optional[StreamChunk]:
        logger.debug(f"Processing chunk: {chunk}")
        if miner_uid == -1:
            # This is a validator response
            try:
                json_object = json.loads(chunk)
            except json.decoder.JSONDecodeError as e:
                logger.error(f"The following error occured when trying to parse JSON chunk '{chunk}': {e}")
                return

            chunk_data = json_object.get("chunk")
            miner_uid = json_object.get("uid", miner_uid)

            if chunk_data is None:
                message = json_object.get("message")
                logger.error(f"Chunk has no data.  Returning message: {message}")
                return self.process_last_chunk(message, miner_uid, validator_uid)
        else:
            # This is a miner response
            chunk_data = chunk

        # Check if we should stream this response
        if self.request.k > len(self.selected_miners):
            # We will choose the first miners that responds
            self.selected_miners.add(miner_uid)
        elif miner_uid not in self.accumulated_chunks:
            # Skip this miner since we have enough
            logger.debug(f"Skipping miner {miner_uid}")
            return

        self.accumulated_chunks[miner_uid].append(chunk_data)
        self.accumulated_timings[miner_uid].append(time.perf_counter() - self.start_time)
        sequence_number = len(self.accumulated_chunks[miner_uid])

        return StreamChunk(
            delta=chunk_data,
            finish_reason=None,
            accumulated_chunks=self.accumulated_chunks[miner_uid],
            accumulated_timings=self.accumulated_timings[miner_uid],
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sequence_number=sequence_number,
            miner_uid=miner_uid,
            validator_uid=validator_uid,
        )

    def process_last_chunk(self, finish_reason: str, miner_uid: int, validator_uid: int) -> StreamChunk:
        if len(self.selected_miners) < self.request.k:
            logger.warning(
                f"Only {len(self.selected_miners)} miners responded, less than the {self.request.k} requested"
            )

        logger.info("Processing of stream finished")
        return StreamChunk(
            delta="",
            finish_reason=finish_reason,
            accumulated_chunks=[],
            accumulated_timings=[time.perf_counter() - self.start_time],
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sequence_number=-1,
            miner_uid=miner_uid,
            validator_uid=validator_uid,
        )
