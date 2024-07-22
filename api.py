import argparse
from fastapi import FastAPI, Request
from validators import QueryValidatorParams, S1ValidatorAPI
from common.schemas import QueryChatRequest, StreamChunkResponse, StreamErrorResponse
from common import utils
import uvicorn
import settings
import openai

client = openai.AsyncClient(api_key=settings.OPENAI_API_KEY)

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


test_app = FastAPI()


@test_app.post("/openai_chat/", response_model=StreamChunkResponse)
async def openai_chat(request: QueryChatRequest):
    """Chat endpoint for the validator"""
    response = await client.chat.completions.create(
        messages=[
            {"role": role, "content": message}
            for role, message in zip(request.roles, request.messages)
        ],
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
    parser = argparse.ArgumentParser(description="Run the validator application.")
    parser.add_argument("--test", action="store_true", help="Run in test mode.")
    args = parser.parse_args()
    if args.test:
        uvicorn.run(
            "api:test_app", host="0.0.0.0", port=8000, loop="asyncio", reload=True
        )
    else:
        validator_instance = S1ValidatorAPI()
        uvicorn.run("api:app", host="0.0.0.0", port=8000, loop="asyncio", reload=True)