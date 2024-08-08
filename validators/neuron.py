import os

import bittensor as bt
from common.schemas import QueryChatRequest
from fastapi.responses import StreamingResponse

from .protocol import StreamPromptingSynapse
from .query_validators import ValidatorStreamManager
from .stream_manager import StreamManager
from .uid_utils import get_top_incentive_uids, get_random_uids

from loguru import logger
import settings


class Neuron:
    def __init__(self):
        self.wallet = bt.wallet(
            name=settings.COLDKEY_WALLET_NAME, hotkey=settings.HOTKEY_WALLET_NAME, path=settings.WALLET_PATH
        )
        self.dendrite = bt.dendrite(wallet=self.wallet)
        self.subtensor = bt.subtensor(network=settings.SUBTENSOR_NETWORK)
        self.metagraph = self.subtensor.metagraph(settings.NETUID)

    def sample_uids(self, params: QueryChatRequest) -> list[int]:
        if params.sampling_mode == "list":
            return params.sampling_list
        if params.sampling_mode == "random":
            uids = get_random_uids(
                metagraph=self.metagraph, wallet=self.wallet, k=params.k, exclude=params.exclude or []
            ).tolist()
            return uids
        if params.sampling_mode == "top_incentive":
            top_uids = get_top_incentive_uids(
                metagraph=self.metagraph, k=params.k, vpermit_tao_limit=settings.QUERY_VPERMIT_TAO_LIMIT
            )

            return top_uids

    async def query_network(self, params: QueryChatRequest) -> StreamingResponse | None:
        # Guess the task name of current request
        # task_name = utils.guess_task_name(params.messages[-1])

        # Get the list of uids to query for this step.
        if settings.QUERY_VALIDATORS:
            logger.debug(f"Querying validators...")
            # As of now we are querying only one validator.
            uids = [settings.QUERY_VALIDATOR_UID]
            logger.debug(f"Querying uids: {uids}")
            axon = self.metagraph.axons[uids[0]]
            # TODO: Remove port setting.
            # Temporary hack to override port, until organic scoring is not in main branch.
            # Currently, two OTF validators are running (one is not setting weights),
            # and port can be overridden by validator without organic scoring.
            if (val_port := settings.QUERY_VALIDATOR_PORT) is not None:
                axon.port = int(val_port)
            axons = [axon]

        else:
            logger.debug(f"Querying miners...")
            uids = self.sample_uids(params)
            axons = [self.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        logger.debug(
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

        if settings.QUERY_VALIDATORS:
            stream_manager = ValidatorStreamManager()
        else:
            stream_manager = StreamManager()

        selected_stream = await stream_manager.process_streams(params.request, streams_responses, uids)
        logger.info(f"Selected stream: {selected_stream}, returning...")
        if selected_stream is None:
            return None

        return selected_stream
