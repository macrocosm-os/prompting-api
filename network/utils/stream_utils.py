from fastapi import HTTPException
import bittensor as bt
from http import HTTPStatus

from network.meta.schemas import QueryChatRequest
from network.utils.uid_utils import is_uid_validator


def validate_request(request: QueryChatRequest, metagraph: "bt.metagraph.Metagraph"):
    """Validates the request object by doing checking of the parameters"""

    if request.k <= 0:
        # Raise bad request error
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Bad request because k must be greater than 0",
        )

    if request.timeout <= 0:
        # Raise timeout error
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_TIMEOUT,
            detail="Request timed out because timeout must be greater than 0",
        )

    if request.sampling_mode == "list" and not request.uid_list:
        # Make sure the uid_list is provided
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="uid_list must be provided when sampling_mode is 'list'",
        )

    if request.query_validators:
        if request.sampling_mode == "list":
            for uid in request.uid_list:
                if not is_uid_validator(metagraph, uid):
                    # Raise error if the UID is not a validator
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND,
                        detail=f"valdiator UID {uid} in uid_list is not found.",
                    )
        elif request.sampling_mode == "top_incentive":
            # Incentive only applies to validators
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="sampling mode of top_incentive only applies to miners",
            )

    if not request.query_validators and request.sampling_mode == "list":
        for uid in request.uid_list:
            if is_uid_validator(metagraph, uid):
                # Raise error if the UID is not a miner
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    detail=f"miner UID {uid} in uid_list is not found.",
                )
