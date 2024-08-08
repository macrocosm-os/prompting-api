import os
import json
import aiofiles
import bittensor as bt
from .streamer import ProcessedStreamResponse


class LogDatabase:
    """
    A class to manage a log database stored as a JSONL (JSON Lines) file.

    Attributes:
        log_database_path (str): The path to the log database file.

    Methods:
        ensure_db_exists(file_path):
            Ensures that the log database file exists. If it doesn't, an empty file is created.

        add_streams_to_db(stream_responses: ProcessedStreamResponse):
            Asynchronously adds stream responses to the log database.

        append_dicts_to_file(file_path, dictionaries):
            Asynchronously appends a list of dictionaries to the specified file.
    """

    def __init__(self, log_database_path: str):
        """
        Initializes the LogDatabase with the given log database file path.

        Args:
            log_database_path (str): The path to the log database file.
        """
        self.log_database_path = log_database_path
        self.ensure_db_exists(log_database_path)

    def ensure_db_exists(self, file_path):
        """
        Ensures that the log database file exists. If it doesn't, creates an empty JSONL file.

        Args:
            file_path (str): The path to the log database file.
        """
        if not os.path.exists(file_path):
            # Create an empty JSONL file
            with open(file_path, "w") as _:
                pass
            # TODO: change log to debug
            bt.logging.info(f"File '{file_path}' created.")
        else:
            bt.logging.info(f"File '{file_path}' already exists.")

    async def add_streams_to_db(self, stream_responses: ProcessedStreamResponse):
        """
        Asynchronously adds stream responses to the log database.

        Args:
            stream_responses (ProcessedStreamResponse): A list of processed stream responses to add to the log database.

        Raises:
            Exception: If an error occurs while adding streams to the database.
        """
        bt.logging.info("Writing streams to the database...")
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
        """
        Asynchronously appends a list of dictionaries to the specified file.

        Args:
            file_path (str): The path to the file where dictionaries will be appended.
            dictionaries (list): A list of dictionaries to append to the file.
        """
        async with aiofiles.open(file_path, mode="a") as file:
            for dictionary in dictionaries:
                await file.write(json.dumps(dictionary) + "\n")
