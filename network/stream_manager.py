import asyncio
import async_timeout
import datetime
import json
from collections import defaultdict
import time
from typing import AsyncIterator, Optional
from loguru import logger

from common.schemas import QueryChatRequest, StreamChunk, StreamError
from network.protocol import StreamPromptingSynapse


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
    ) -> AsyncIterator[bytes]:
        """Generates a stream of responses from miners or validators to the API

        Args:
            streams_responses (list[AsyncIterator]): responses from miners (or miners through validators)
            stream_uids (Optional[list[int]]): the validator or miner UID that produced the stream

        Returns:
            AsyncIterator[bytes]: processed byte stream of responses
        """

        self.accumulated_chunks = defaultdict(list)
        self.accumulated_timings = defaultdict(list)
        self.start_time = time.perf_counter()

        try:
            async with async_timeout.timeout(self.request.timeout):
                for stream_response, uid in zip(streams_responses, stream_uids):
                    # Determine which UID was passed in
                    validator_uid = uid if self.request.query_validators else -1
                    miner_uid = uid if not self.request.query_validators else -1
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
                            yield self.generate_last_chunk(miner_uid, validator_uid)
        except asyncio.TimeoutError:
            logger.error(f"Stream timed out after {self.request.timeout} seconds")
            yield self.generate_error_chunk("timed out")

    def split_chunks(self, raw_chunk: str) -> list[str]:
        """This splits received chunks into a list of chunks
        Input: "{chunk1}{chunk2}..."
        Output: ["{chunk1}", "{chunk2}", ...]

        Notes:
         - Requires the `delm` to not already exist in the `raw_chunk`
        """
        delm = ">>|break|<<"
        return raw_chunk.replace("}{", "}" + delm + "{").split(delm)

    def process_chunk(self, chunk: str, miner_uid: int = -1, validator_uid: int = -1) -> Optional[StreamChunk]:
        """Processes a chunk of data from a miner (or miner through a validator) and streams it back
           through the API

        Args:
            chunk (str): miner response
            miner_uid (int): miner UID (-1 if from a validator - we'll get the miner UID from the chunk)
            validator_uid (int): validator UID (-1 if direct from a miner)

        Returns:
            Optional[StreamChunk]: If it's a valid chunk, returns a StreamChunk object, otherwise None
        """
        logger.debug(f"Processing chunk: {chunk}")

        # Validators usually return JSON but miners don't unless its an error (has a message)
        try:
            json_object = json.loads(chunk)
        except json.decoder.JSONDecodeError:
            # If we didn't get a JSON response, it could due to a validator who hasn't upgraded or due to a normal miner response
            json_object = {}

        chunk_delta = json_object.get("chunk", chunk)
        miner_uid = json_object.get("uid", miner_uid)

        if message := json_object.get("message"):
            return self.generate_error_chunk(message, miner_uid, validator_uid)

        # Check if we should stream this response
        if self.request.k > len(self.selected_miners):
            # We will choose the first miners that responds
            self.selected_miners.add(miner_uid)
        elif miner_uid not in self.accumulated_chunks:
            # Skip this miner since we have enough
            logger.debug(f"Skipping miner {miner_uid}")
            return

        self.accumulated_chunks[miner_uid].append(chunk_delta)
        self.accumulated_timings[miner_uid].append(time.perf_counter() - self.start_time)
        sequence_number = len(self.accumulated_chunks[miner_uid])

        return StreamChunk(
            delta=chunk_delta,
            finish_reason=None,
            accumulated_chunks=self.accumulated_chunks[miner_uid],
            accumulated_timings=self.accumulated_timings[miner_uid],
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sequence_number=sequence_number,
            miner_uid=miner_uid,
            validator_uid=validator_uid,
        )

    def generate_last_chunk(self, miner_uid: int = -1, validator_uid: int = -1) -> StreamChunk:
        """Generates the last chunk of the stream with a finish reason.
        If we're streaming multiple miners, we'll still only send one last "completed"
        chunk for the whole stream.
        """
        if len(self.selected_miners) < self.request.k and validator_uid != -1:
            # only show warning if we queried validators (we have a validator UID) because miners send last
            # chunk for each of their own streams and this warning would erroneously be logged if this was
            # the first miner and k > 1.  This works for validators because they only send the last chunk
            # after streaming all miner responses
            logger.warning(
                f"Only {len(self.selected_miners)} miners responded, less than the {self.request.k} requested"
            )

        logger.info("Processing of stream finished")
        return StreamChunk(
            delta="",
            finish_reason="completed",
            accumulated_chunks=[],
            accumulated_timings=[time.perf_counter() - self.start_time],
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sequence_number=-1,
            miner_uid=miner_uid,
            validator_uid=validator_uid,
        )

    def generate_error_chunk(self, error: str, miner_uid: int = -1, validator_uid: int = -1) -> StreamError:
        """Generates an error chunk to be streamed back through the API"""
        logger.error(f"Chunk has no data.  Returning error: {error}")
        return StreamError(
            error=error,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sequence_number=-1,
            miner_uid=miner_uid,
            validator_uid=validator_uid,
        )
