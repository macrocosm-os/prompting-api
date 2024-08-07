import argparse
import os

import bittensor as bt
from validators.protocol import StreamPromptingSynapse
from common.schemas import QueryChatRequest

# from aiohttp.web_response import Response, StreamResponse
from fastapi.responses import StreamingResponse

# from prompting.utils.uids import get_random_uids
# from prompting.validator import Validator

from .query_validators import ValidatorStreamManager
from .stream_manager import StreamManager

# from .validator_utils import get_top_incentive_uids
from common.config import add_args, config
from loguru import logger


class Neuron:
    def __init__(self, query_validators: bool = True):
        self._query_validators = query_validators
        self.config = self._config()
        logger.debug(f"Config: {self.config}")

        self.wallet = bt.wallet(config=self.config)
        self.dendrite = bt.dendrite(wallet=self.wallet)
        self.subtensor = bt.subtensor(config=self.config)
        self.metagraph = self.subtensor.metagraph(self.config.netuid)

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser):
        add_args(cls, parser)

    @classmethod
    def _config(cls):
        return config(cls)

    def sample_uids(self, params: QueryChatRequest) -> list[int]:
        return [218]
        # return [213]
        if params.sampling_mode == "random":
            uids = get_random_uids(self.validator, k=params.k, exclude=params.exclude or []).tolist()
            return uids
        if params.sampling_mode == "top_incentive":
            metagraph = self.validator.metagraph
            vpermit_tao_limit = self.validator.config.neuron.vpermit_tao_limit

            top_uids = get_top_incentive_uids(metagraph, k=params.k_miners, vpermit_tao_limit=vpermit_tao_limit)

            return top_uids

    async def query_validator(self, params: QueryChatRequest) -> StreamingResponse | None:
        # Guess the task name of current request
        # task_name = utils.guess_task_name(params.messages[-1])

        # Get the list of uids to query for this step.
        if self._query_validators:
            logger.debug(f"Querying validators...")
            # As of now we are querying only OTF validatior.
            uids = [self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)]
            axon = self.metagraph.axons[uids[0]]
            # TODO: Remove port setting.
            # Temporary hack to override port, until organic scoring is not in main branch.
            # Currently, two OTF validators are running (one is not setting weights),
            # and port can be overridden by validator without organic scoring.
            if (val_port := os.environ.get("VAL_PORT")) is not None:
                axon.port = int(val_port)
            axons = [axon]

        else:
            logger.debug(f"Querying miners...")
            uids = self.sample_uids(params)
            axons = [self.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        logger.info(
            f"Sampling dendrite by {params.sampling_mode} with roles {params.roles} and messages {params.messages}"
        )

        streams_responses = await self.dendrite(
            axons=axons,
            synapse=StreamPromptingSynapse(roles=params.roles, messages=params.messages),
            timeout=params.timeout,
            deserialize=False,
            streaming=True,
        )

        logger.info(f"Completed sampling dendrite with uids: {uids}. Streams_responses: {streams_responses}")

        if self._query_validators:
            stream_manager = ValidatorStreamManager()
        else:
            stream_manager = StreamManager()
        logger.info(f"Responses: {streams_responses}")
        selected_stream = await stream_manager.process_streams(params.request, streams_responses, uids)
        logger.info(f"Selected stream: {selected_stream}, returning...")
        if selected_stream is None:
            return None
        # return StreamingResponse(content=selected_stream, media_type="application/json")
        return selected_stream
        # return selected_stream