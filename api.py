
import json
import asyncio

import traceback
import bittensor as bt

import utils

from typing import List
from neurons.validator import Validator
from prompting.forward import handle_response
from prompting.dendrite import DendriteResponseEvent
from prompting.protocol import PromptingSynapse, StreamPromptingSynapse
from prompting.utils.uids import get_random_uids

from aiohttp import web

from aiohttp.web_response import Response


async def single_response(validator: Validator, messages: List[str], roles: List[str], k: int = 5, timeout: float = 3.0, exclude: List[int] = None, prefer: str = 'longest') -> Response:

    try:
        # Guess the task name of current request
        task_name = utils.guess_task_name(messages[-1])

        # Get the list of uids to query for this step.
        uids = get_random_uids(validator, k=k, exclude=exclude or []).tolist()
        axons = [validator.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        bt.logging.info(f'Calling dendrite')
        responses = await validator.dendrite(
            axons=axons,
            synapse=PromptingSynapse(roles=roles, messages=messages),
            timeout=timeout,
        )

        bt.logging.info(f"Creating DendriteResponseEvent:\n {responses}")
        # Encapsulate the responses in a response event (dataclass)
        response_event = DendriteResponseEvent(responses, uids)

        # convert dict to json
        response = response_event.__state_dict__()

        response['completion_is_valid'] = valid = list(map(utils.completion_is_valid, response['completions']))
        valid_completions = [response['completions'][i] for i, v in enumerate(valid) if v]

        response['task_name'] = task_name
        response['ensemble_result'] = utils.ensemble_result(valid_completions, task_name=task_name, prefer=prefer)

        bt.logging.info(f"Response:\n {response}")
        return Response(status=200, reason="I can't believe it's not butter!", text=json.dumps(response))

    except Exception:
        bt.logging.error(f'Encountered in {single_response.__name__}:\n{traceback.format_exc()}')
        return Response(status=500, reason="Internal error")


async def stream_response(validator: Validator, messages: List[str], roles: List[str], k: int = 5, timeout: float = 3.0, exclude: List[int] = None, prefer: str = 'longest') -> web.StreamResponse:

    try:
        # Guess the task name of current request
        task_name = utils.guess_task_name(messages[-1])

        # Get the list of uids to query for this step.
        uids = get_random_uids(validator, k=k, exclude=exclude or []).tolist()
        axons = [validator.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        bt.logging.info(f'Calling dendrite')
        streams_responses = await validator.dendrite(
            axons=axons,
            synapse=StreamPromptingSynapse(roles=roles, messages=messages),
            timeout=timeout,
            deserialize=False,
            streaming=True,
        )

        # Prepare the task for handling stream responses
        handle_stream_responses_task = asyncio.create_task(
            handle_response(responses=dict(zip(uids, streams_responses)))
        )

        stream_results = await handle_stream_responses_task

        responses = [stream_result.synapse for stream_result in stream_results]
        bt.logging.info(f"Creating DendriteResponseEvent:\n {responses}")
        # Encapsulate the responses in a response event (dataclass)
        response_event = DendriteResponseEvent(responses, uids)

        # convert dict to json
        response = response_event.__state_dict__()

        response['completion_is_valid'] = valid = list(map(utils.completion_is_valid, response['completions']))
        valid_completions = [response['completions'][i] for i, v in enumerate(valid) if v]

        response['task_name'] = task_name
        response['ensemble_result'] = utils.ensemble_result(valid_completions, task_name=task_name, prefer=prefer)

        bt.logging.info(f"Response:\n {response}")
        return Response(status=200, reason="I can't believe it's not butter!", text=json.dumps(response))

    except Exception:
        bt.logging.error(f'Encountered in {single_response.__name__}:\n{traceback.format_exc()}')
        return Response(status=500, reason="Internal error")