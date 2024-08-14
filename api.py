import uvicorn
import asyncio
from fastapi import FastAPI, Request, Body, Depends
from fastapi.security import APIKeyHeader
from contextlib import asynccontextmanager
from loguru import logger

from network.neuron import Neuron
from network import echo
from network.meta.schemas import QueryChatRequest, StreamChunk
from network.meta.middlewares import middleware
import settings

instance = Neuron()


async def periodic_metagraph_resync():
    """Function to periodically resync the metagraph every 60 seconds."""
    try:
        while True:
            await asyncio.sleep(settings.RESYNC_METAGRAPH_INTERVAL)
            logger.info("Resyncing metagraph...")
            instance.resync_metagraph()
    except asyncio.CancelledError:
        logger.info("Periodic metagraph resync task has been shutdown.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Start the periodic task
    task = asyncio.create_task(periodic_metagraph_resync())
    logger.info("Started the periodic metagraph resync background task.")
    try:
        yield
    finally:
        # Shutdown logic: Cancel the periodic task
        task.cancel()
        await task  # Wait for the task to be cancelled
        logger.info("Finished shutting down the application.")


security = APIKeyHeader(name="api_key", auto_error=False)
app = FastAPI(middleware=middleware, lifespan=lifespan)


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
    return await instance.query_network(query)


@app.post(
    "/echo/",
    response_model=StreamChunk,
    responses={400: {"description": "Bad request"}},
)
async def echo_stream(request: Request, query: QueryChatRequest, authorization: str = Depends(security)):
    return await echo.echo_stream(request)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, loop="asyncio", reload=True)
