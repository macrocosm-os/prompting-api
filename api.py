import uvicorn
from fastapi import FastAPI, Request, Body, Depends
from fastapi.security import APIKeyHeader

from network.neuron import Neuron

from common.schemas import QueryChatRequest, StreamChunk
from common import utils
from common.middlewares import middleware

app = FastAPI(middleware=middleware)
security = APIKeyHeader(name="api_key", auto_error=False)
instance = Neuron()


@app.post(
    "/chat/",
    responses={
        200: {"model": StreamChunk},
        400: {"description": "Bad request"},
        504: {"description": "Timed out"},
    },
)
async def chat(
    request: Request,
    query: QueryChatRequest = Body(...),
    authorization: str = Depends(security),
):
    """Chat endpoint for the validator"""

    query.request = request
    return await instance.query_network(query)


@app.post(
    "/echo/",
    response_model=StreamChunk,
    responses={400: {"description": "Bad request"}},
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
    uvicorn.run("api:app", host="0.0.0.0", port=8002, loop="asyncio", reload=True)
