from fastapi import FastAPI, Request, Body, Depends
from fastapi.security import APIKeyHeader

from loguru import logger
from common.schemas import QueryChatRequest, StreamChunkResponse, StreamErrorResponse
from common import utils
import uvicorn
from common.middlewares import middleware
from network.neuron import Neuron

app = FastAPI(middleware=middleware)
security = APIKeyHeader(name="api_key", auto_error=False)
instance = Neuron()


@app.post(
    "/chat/",
    responses={400: {"model": StreamErrorResponse}},
)
async def chat(request: Request, query: QueryChatRequest = Body(...), authorization: str = Depends(security)):
    """Chat endpoint for the validator"""
    try:
        query.request = request
        return await instance.query_network(query)
    except Exception as e:
        logger.exception(e)


@app.post(
    "/echo/",
    response_model=StreamChunkResponse,
    responses={400: {"model": StreamErrorResponse}},
)
async def echo_stream(request: Request, query: QueryChatRequest, authorization: str = Depends(security)):
    return await utils.echo_stream(request)


test_app = FastAPI(middleware=middleware)


if __name__ == "__main__":
    # Note that the arguments to this file are forwarded to bittensor, even though no
    # argparse is used here.
    # parser = argparse.ArgumentParser(description="Run the validator application.")
    # parser.add_argument("--test", action="store_true", help="Run in test mode.")
    # args = parser.parse_args()
    # if args.test:
    #     uvicorn.run(
    #         "api:test_app", host="0.0.0.0", port=8000, loop="asyncio", reload=True
    #     )
    # else:
    uvicorn.run("api:app", host="0.0.0.0", port=8000, loop="asyncio", reload=True)
