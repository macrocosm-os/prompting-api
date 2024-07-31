import os

import bittensor as bt
from aiohttp.web_response import Response, StreamResponse
from prompting.protocol import StreamPromptingSynapse
from prompting.utils.uids import get_random_uids
from prompting.validator import Validator

from .base import QueryValidatorParams, ValidatorAPI
from .query_validators import ValidatorStreamManager
from .stream_manager import StreamManager
from .validator_utils import get_top_incentive_uids


class S1ValidatorAPI(ValidatorAPI):
    def __init__(self, query_validators: bool = True):
        self.validator = Validator()
        self._query_validators = query_validators
    
    def sample_uids(self, params: QueryValidatorParams) -> list[int]:
        if params.sampling_mode == "random":
            uids = get_random_uids(
                self.validator, k=params.k_miners, exclude=params.exclude or []
            ).tolist()
            return uids
        if params.sampling_mode == "top_incentive":
            metagraph = self.validator.metagraph
            vpermit_tao_limit = self.validator.config.neuron.vpermit_tao_limit

            top_uids = get_top_incentive_uids(
                metagraph, k=params.k_miners, vpermit_tao_limit=vpermit_tao_limit
            )

            return top_uids

    async def get_stream_response(self, params: QueryValidatorParams) -> StreamResponse:
        # Guess the task name of current request
        # task_name = utils.guess_task_name(params.messages[-1])

        # Get the list of uids to query for this step.
        if self._query_validators:
            # As of now we are querying only OTF validatior.
            uids = [self.validator.metagraph.hotkeys.index(self.validator.wallet.hotkey.ss58_address)]
            axon = self.validator.metagraph.axons[uids[0]]
            # TODO: Remove port setting.
            # Temporary hack to override port, until organic scoring is not in main branch.
            # Currently, two OTF validators are running (one is not setting weights),
            # and port can be overridden by validator without organic scoring.
            if (val_port := os.environ.get("VAL_PORT")) is not None:
                axon.port = int(val_port)
            axons = [axon]

        else:
            uids = self.sample_uids(params)
            axons = [self.validator.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        bt.logging.info(
            f"Sampling dendrite by {params.sampling_mode} with roles {params.roles} and messages {params.messages}"
        )

        streams_responses = await self.validator.dendrite(
            axons=axons,
            synapse=StreamPromptingSynapse(
                roles=params.roles, messages=params.messages
            ),
            timeout=params.timeout,
            deserialize=False,
            streaming=True,
        )

        if self._query_validators:
            stream_manager = ValidatorStreamManager()
        else:
            stream_manager = StreamManager()
        selected_stream = await stream_manager.process_streams(params.request, streams_responses, uids)

        return selected_stream

    async def query_validator(self, params: QueryValidatorParams) -> Response:
        return await self.get_stream_response(params)
