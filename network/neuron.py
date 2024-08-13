import bittensor as bt
from fastapi.responses import StreamingResponse
from typing import Optional
from loguru import logger

from network.stream_utils import validate_request
from network.protocol import StreamPromptingSynapse
from network.stream_manager import StreamManager
from network.uid_utils import sample_uids
from common.schemas import QueryChatRequest
import settings


class Neuron:
    def __init__(self):
        self.wallet = bt.wallet(
            name=settings.COLDKEY_WALLET_NAME,
            hotkey=settings.HOTKEY_WALLET_NAME,
            path=settings.WALLET_PATH,
        )
        self.dendrite = bt.dendrite(wallet=self.wallet)
        self.subtensor = bt.subtensor(network=settings.SUBTENSOR_NETWORK)
        self.metagraph = self.subtensor.metagraph(settings.NETUID)

    async def query_network(self, params: QueryChatRequest) -> Optional[StreamingResponse]:
        # Validate the request parameters
        validate_request(params, self.metagraph)

        # Get the UIDs (and axons) to query
        uids = sample_uids(self.metagraph, self.wallet, params)
        logger.debug(f"Querying uids: {uids}")
        axons = [self.metagraph.axons[uid] for uid in uids]

        if params.query_validators:
            logger.debug("Querying validators...")

            # Currently, two OTF validators are running (one is not setting weights),
            # and we may need to specify which validator to consider by setting to our desired port.
            if (val_port := settings.QUERY_VALIDATOR_PORT) is not None:
                for axon in axons:
                    axon.port = int(val_port)
        else:
            logger.debug("Querying miners...")

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

        stream_manager = StreamManager(params)
        selected_stream = StreamingResponse(
            stream_manager.stream_generator(streams_responses, uids),
            media_type="text/event-stream",
        )

        logger.info(f"Selected stream: {selected_stream}, returning...")
        if selected_stream is None:
            return None

        return selected_stream
