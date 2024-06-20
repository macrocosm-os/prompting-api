import os
import json
import aiofiles
import bittensor as bt
from .streamer import ProcessedStreamResponse


class LogDatabase:
    def __init__(self, log_database_path: str):
        self.log_database_path = log_database_path
        self.ensure_db_exists(log_database_path)

    def ensure_db_exists(self, file_path):
        if not os.path.exists(file_path):
            # Create an empty JSONL file
            with open(file_path, "w") as file:
                pass
            # TODO: change log to debug
            bt.logging.info(f"File '{file_path}' created.")
        else:
            bt.logging.info(f"File '{file_path}' already exists.")

    async def add_streams_to_db(self, stream_responses: ProcessedStreamResponse):
        bt.logging.info(f"Writing streams to the database...")
        try:
            stream_responses_dict = [
                dict(stream_response) for stream_response in stream_responses
            ]
            await self.append_dicts_to_file(
                self.log_database_path, stream_responses_dict
            )
            bt.logging.success("Streams added to the database.")
        except Exception as e:
            bt.logging.error(f"Error while adding streams to the database: {e}")
            raise e

    async def append_dicts_to_file(self, file_path, dictionaries):
        async with aiofiles.open(file_path, mode="a") as file:
            for dictionary in dictionaries:
                await file.write(json.dumps(dictionary) + "\n")
