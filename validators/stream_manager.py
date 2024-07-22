import asyncio
import bittensor as bt
from .streamer import AsyncResponseDataStreamer
from .database import LogDatabase
from typing import List, AsyncIterator
from aiohttp.web import Request


class StreamManager:
    """
    A class to manage the processing of multiple asynchronous data streams and log their responses.

    Attributes:
        log_database (LogDatabase): The log database to store stream responses.

    Methods:
        process_streams(request, streams_responses, stream_uids):
            Processes multiple asynchronous streams, logs their responses, and returns the selected stream response.
    """

    def __init__(self, log_database_path: str = "requests_db.jsonl"):
        """
        Initializes the StreamManager with the given log database file path.

        Args:
            log_database_path (str): The path to the log database file, defaults to "requests_db.jsonl".
        """
        self.log_database = LogDatabase(log_database_path)

    async def process_streams(
        self,
        request: Request,
        streams_responses: List[AsyncIterator],
        stream_uids: List[int],
    ):
        """
        Processes multiple asynchronous streams, logs their responses, and returns the selected stream response (stream from first non-empty chunk).

        Args:
            request (Request): The web request object.
            streams_responses (List[AsyncIterator]): A list of asynchronous iterators representing the streams.
            stream_uids (List[int]): A list of unique IDs for the streams.

        Returns:
            ProcessedStreamResponse: The response from the selected stream.
        """
        lock = asyncio.Lock()

        streamers = [
            AsyncResponseDataStreamer(
                async_iterator=stream, selected_uid=stream_uid, lock=lock
            )
            for stream, stream_uid in zip(streams_responses, stream_uids)
        ]
        completed_streams = await asyncio.gather(
            *[streamer.stream(request) for streamer in streamers]
        )

        lock.release()
        bt.logging.info(f"Streams from uids: {stream_uids} processing completed.")

        await self.log_database.add_streams_to_db(completed_streams)
        # Gets the first stream that acquired the lock, meaning the first stream that was able to return a non-empty chunk
        selected_stream = next(
            (
                completed_stream
                for streamer, completed_stream in zip(streamers, completed_streams)
                if streamer.lock_acquired
            ),
            None,
        )

        return selected_stream
