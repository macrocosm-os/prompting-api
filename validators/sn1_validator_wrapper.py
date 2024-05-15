import random
import bittensor as bt
from prompting.validator import Validator
from prompting.utils.uids import get_random_uids
from prompting.protocol import StreamPromptingSynapse
from .base import QueryValidatorParams, ValidatorAPI
from aiohttp.web_response import Response, StreamResponse
from dataclasses import dataclass
from typing import List
from .streamer import AsyncResponseDataStreamer


@dataclass
class ProcessedStreamResponse:
    streamed_chunks: List[str]
    streamed_chunks_timings: List[float]
    synapse: StreamPromptingSynapse


class S1ValidatorAPI(ValidatorAPI):
    def __init__(self):
        self.validator = Validator()


    async def get_stream_response(self, params: QueryValidatorParams) -> StreamResponse:
        # Guess the task name of current request
        # task_name = utils.guess_task_name(params.messages[-1])

        # Get the list of uids to query for this step.
        uids = get_random_uids(
            self.validator, k=params.k_miners, exclude=params.exclude or []
        ).tolist()
        axons = [self.validator.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        bt.logging.info(f"Calling dendrite")

        streams_responses = await self.validator.dendrite(
            axons=axons,
            synapse=StreamPromptingSynapse(
                roles=params.roles, messages=params.messages
            ),
            timeout=params.timeout,
            deserialize=False,
            streaming=True,
        )
        uid_stream_dict = dict(zip(uids, streams_responses))
        random_uid, random_stream = random.choice(list(uid_stream_dict.items()))                        
        
        # Creates a streamer from the selected stream
        streamer = AsyncResponseDataStreamer(async_iterator=random_stream, selected_uid=random_uid)        
        response = await streamer.stream(params.request)                        
        return response

    async def query_validator(self, params: QueryValidatorParams) -> Response:
        return await self.get_stream_response(params)
