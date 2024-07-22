from fastapi import FastAPI
from common.schemas import StreamChunkResponse, QueryChatRequest
from settings import OPENAI_API_KEY
from openai import AsyncClient

client = AsyncClient(api_key=OPENAI_API_KEY)


app = FastAPI()


@app.post("/openai_chat/", response_model=StreamChunkResponse)
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
