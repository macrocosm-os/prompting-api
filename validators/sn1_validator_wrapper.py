import json
import utils
import torch
import traceback
import time
import random
import bittensor as bt
from typing import Awaitable
from prompting.validator import Validator
from prompting.utils.uids import get_random_uids
from prompting.protocol import PromptingSynapse, StreamPromptingSynapse
from prompting.dendrite import DendriteResponseEvent
from .base import QueryValidatorParams, ValidatorAPI
from aiohttp.web_response import Response, StreamResponse
from deprecated import deprecated
from dataclasses import dataclass
from typing import List
from responses import TextStreamResponse


@dataclass
class ProcessedStreamResponse:
    streamed_chunks: List[str]
    streamed_chunks_timings: List[float]
    synapse: StreamPromptingSynapse


class S1ValidatorAPI(ValidatorAPI):
    def __init__(self):
        self.validator = Validator()

    @deprecated(
        reason="This function is deprecated. Validators use stream synapse now, use get_stream_response instead."
    )
    async def get_response(self, params: QueryValidatorParams) -> Response:
        try:
            # Guess the task name of current request
            task_name = utils.guess_task_name(params.messages[-1])

            # Get the list of uids to query for this step.
            uids = get_random_uids(
                self.validator, k=params.k_miners, exclude=params.exclude or []
            ).tolist()
            axons = [self.validator.metagraph.axons[uid] for uid in uids]

            # Make calls to the network with the prompt.
            bt.logging.info(f"Calling dendrite")
            responses = await self.validator.dendrite(
                axons=axons,
                synapse=PromptingSynapse(roles=params.roles, messages=params.messages),
                timeout=params.timeout,
            )

            bt.logging.info(f"Creating DendriteResponseEvent:\n {responses}")
            # Encapsulate the responses in a response event (dataclass)
            response_event = DendriteResponseEvent(
                responses, torch.LongTensor(uids), params.timeout
            )

            # convert dict to json
            response = response_event.__state_dict__()

            response["completion_is_valid"] = valid = list(
                map(utils.completion_is_valid, response["completions"])
            )
            valid_completions = [
                response["completions"][i] for i, v in enumerate(valid) if v
            ]

            response["task_name"] = task_name
            response["ensemble_result"] = utils.ensemble_result(
                valid_completions, task_name=task_name, prefer=params.prefer
            )

            bt.logging.info(f"Response:\n {response}")
            return Response(
                status=200,
                reason="I can't believe it's not butter!",
                text=json.dumps(response),
            )

        except Exception:
            bt.logging.error(
                f"Encountered in {self.__class__.__name__}:get_response:\n{traceback.format_exc()}"
            )
            return Response(status=500, reason="Internal error")

    async def process_response(
        self, response: StreamResponse, async_generator: Awaitable
    ) -> ProcessedStreamResponse:
        """Process a single response asynchronously."""
        # Initialize chunk with a default value
        chunk = None
        # Initialize chunk array to accumulate streamed chunks
        chunks = []
        chunks_timings = []

        start_time = time.time()
        last_sent_index = 0
        async for chunk in async_generator:
            if isinstance(chunk, list):
                # Chunks are currently returned in string arrays, so we need to concatenate them
                concatenated_chunks = "".join(chunk)
                new_data = concatenated_chunks[last_sent_index:]

                if new_data:
                    await response.write(new_data.encode("utf-8"))
                    bt.logging.info(f"Received new chunk from miner: {chunk}")
                    last_sent_index += len(new_data)
                    chunks.extend(chunk)
                    chunks_timings.append(time.time() - start_time)

        if chunk is not None and isinstance(chunk, StreamPromptingSynapse):
            # Assuming the last chunk holds the last value yielded which should be a synapse with the completion filled
            return ProcessedStreamResponse(
                synapse=chunk,
                streamed_chunks=chunks,
                streamed_chunks_timings=chunks_timings,
            )
        else:
            raise ValueError("The last chunks not a StreamPrompting synapse")

    async def get_stream_response(self, params: QueryValidatorParams) -> StreamResponse:
        response = StreamResponse(status=200, reason="OK")
        response.headers["Content-Type"] = "application/json"

        await response.prepare(params.request)  # Prepare and send the headers

        try:
            # Guess the task name of current request
            # task_name = utils.guess_task_name(params.messages[-1])

            # Get the list of uids to query for this step.
            uids = get_random_uids(
                self.validator, k=params.k_miners, exclude=params.exclude or []
            ).tolist()
            axons = [self.validator.metagraph.axons[uid] for uid in uids]

            # Make calls to the network with the prompt.
            bt.logging.info(f"Calling dendrite")
            start_time = time.time()

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
            processed_response = await self.process_response(response, random_stream)

            # Prepare final JSON chunk
            response_data = json.dumps(
                TextStreamResponse(
                    streamed_chunks=processed_response.streamed_chunks,
                    streamed_chunks_timings=processed_response.streamed_chunks_timings,
                    uid=random_uid,
                    completion=processed_response.synapse.completion,
                    timing=time.time() - start_time,
                ).to_dict()
            )

            # Send the final JSON as part of the stream
            await response.write(json.dumps(response_data).encode("utf-8"))
        except Exception as e:
            bt.logging.error(
                f"Encountered an error in {self.__class__.__name__}:get_stream_response:\n{traceback.format_exc()}"
            )
            response.set_status(500, reason="Internal error")
            await response.write(json.dumps({"error": str(e)}).encode("utf-8"))
        finally:
            await response.write_eof()  # Ensure to close the response properly

        return response

    async def query_validator(self, params: QueryValidatorParams) -> Response:
        return await self.get_stream_response(params)
