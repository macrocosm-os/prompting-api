
from collections import defaultdict
import json
import random
from typing import AsyncIterator
from prompting.protocol import StreamPromptingSynapse
import bittensor as bt


def sample_hotkey_uids(validator, hotkeys: list[str], k: int = 1) -> list[int]:
    """Sample k unique UIDs from the list of hotkeys. Returns all UIDs if the number of hotkeys is less than k."""
    uids = [validator.metagraph.hotkeys.index(hotkey) for hotkey in hotkeys]
    return random.sample(uids, min(k, len(uids)))


async def split_responses_by_uid(async_generators: list[AsyncIterator[str]]) -> dict[int, AsyncIterator[str]]:
    """Split async_generator into multiple async generators based on UID."""
    uid_to_chunks = defaultdict(list)

    for async_generator in async_generators:
        async for chunk in async_generator:
            if isinstance(chunk, str):
                if not chunk:
                    continue

                if "}{" in chunk:
                    # If multiple chunks arrived in one sample.
                    json_objects = chunk.split("}{")
                    json_objects = [obj if obj.startswith("{") else "{" + obj for obj in json_objects]
                    json_objects = [obj if obj.endswith("}") else obj + "}" for obj in json_objects]

                    # Parse each JSON object.
                    for obj in json_objects:
                        try_parse_json(obj, uid_to_chunks)
                else:
                    try_parse_json(chunk, uid_to_chunks)
    validator_synapse: StreamPromptingSynapse = chunk

    for uid, chunks in uid_to_chunks.items():
        synapse = StreamPromptingSynapse(
            roles=validator_synapse.roles,
            messages=validator_synapse.messages,
            completion="".join(chunks),
        )
        uid_to_chunks[uid].append(synapse)

    # Convert lists of chunks into async generators
    async def create_async_generator(chunks: list[str]) -> AsyncIterator[str]:
        for chunk in chunks:
            yield chunk

    return {uid: create_async_generator(chunks) for uid, chunks in uid_to_chunks.items()}


def try_parse_json(json_object: str, uid_to_chunks: dict[int, str]):
    """Try to parse JSON and populate uid_to_chunks with the data."""
    try: 
        data = json.loads(json_object)
        uid_to_chunks[data["uid"]].append(data["chunk"])
    except json.decoder.JSONDecodeError as e:
        bt.logging.error(f"An error occured when trying to parse JSON chunk: {e}")
