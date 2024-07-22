from fastapi import FastAPI, Request
from validators import QueryValidatorParams, S1ValidatorAPI
from common.schemas import QueryChatRequest, StreamChunkResponse, StreamErrorResponse
from common import utils

validator_instance = S1ValidatorAPI()
app = FastAPI()


@app.post(
    "/chat/",
    response_model=StreamChunkResponse,
    responses={400: {"model": StreamErrorResponse}},
)
async def chat(request: Request, query: QueryChatRequest):
    """Chat endpoint for the validator"""
    params = QueryValidatorParams.from_request(request)
    response = await validator_instance.query_validator(params)
    return response


@app.post(
    "/echo/",
    response_model=StreamChunkResponse,
    responses={400: {"model": StreamErrorResponse}},
)
async def echo_stream(request: Request, query: QueryChatRequest):
    return await utils.echo_stream(request)
