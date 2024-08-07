from fastapi import FastAPI, Request, Body, Depends
from fastapi.security import APIKeyHeader

from loguru import logger
from common.schemas import QueryChatRequest, StreamChunkResponse, StreamErrorResponse
from common import utils
import uvicorn
import settings
import openai
from common.middlewares import middleware
from validators.neuron import Neuron

client = openai.AsyncClient(api_key=settings.OPENAI_API_KEY)

app = FastAPI(middleware=middleware)
security = APIKeyHeader(name="api_key", auto_error=False)
instance = Neuron(query_validators=False)


@app.post(
    "/chat/",
    responses={400: {"model": StreamErrorResponse}},
)
async def chat(request: Request, query: QueryChatRequest = Body(...), authorization: str = Depends(security)):
    """Chat endpoint for the validator"""
    try:
        query.request = request
        return await instance.query_validator(query)
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


@test_app.post("/openai_chat/", response_model=StreamChunkResponse)
async def openai_chat(request: QueryChatRequest):
    """Chat endpoint for the validator"""
    response = await client.chat.completions.create(
        messages=[{"role": role, "content": message} for role, message in zip(request.roles, request.messages)],
        model="gpt-3.5-turbo",
        n=request.k,
    )
    return StreamChunkResponse(
        delta=response.choices[0].message.content,
        finish_reason="completed",
        accumulated_chunks=[response.choices[0].message.content],
        accumulated_chunks_timings=[response.created],
        timestamp=str(response.created),
        sequence_number=0,
        selected_uid=1,
    )


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
