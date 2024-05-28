import random
import bittensor as bt
from prompting.validator import Validator
from prompting.utils.uids import get_random_uids
from prompting.protocol import StreamPromptingSynapse
from .base import QueryValidatorParams, ValidatorAPI
from aiohttp.web_response import Response, StreamResponse
from .streamer import AsyncResponseDataStreamer
from .validator_utils import get_top_incentive_uids


class S1ValidatorAPI(ValidatorAPI):
    def __init__(self):
        self.validator = Validator()

    def sample_uids(self, params: QueryValidatorParams):    
        if params.sampling_mode == "random":
            uids = get_random_uids(
                self.validator, k=params.k_miners, exclude=params.exclude or []
            ).tolist()
            return uids
        if params.sampling_mode == "top_incentive":
            metagraph = self.validator.metagraph
            vpermit_tao_limit = self.validator.config.neuron.vpermit_tao_limit
            
            top_uids = get_top_incentive_uids(metagraph, k=params.k_miners, vpermit_tao_limit=vpermit_tao_limit)
            
            return top_uids

    async def get_stream_response(self, params: QueryValidatorParams) -> StreamResponse:
        # Guess the task name of current request
        # task_name = utils.guess_task_name(params.messages[-1])

        # Get the list of uids to query for this step.
        uids =  self.sample_uids(params)
        axons = [self.validator.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        bt.logging.info(f"Sampling dendrite by {params.sampling_mode} with roles {params.roles} and messages {params.messages}")

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
