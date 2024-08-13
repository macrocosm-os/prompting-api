import asyncio
from fastapi import Request
from fastapi.responses import StreamingResponse


# Simulate the stream synapse for the echo endpoint
class EchoAsyncIterator:
    def __init__(self, message: str, k: int, delay: float):
        self.message = message
        self.k = k
        self.delay = delay

    async def __aiter__(self):
        for _ in range(self.k):
            for word in self.message.split():
                s_word = f"{word} "
                print(s_word, end="")
                yield s_word
                await asyncio.sleep(self.delay)


async def echo_stream(request: Request) -> StreamingResponse:
    request_data = await request.json()
    k = request_data.get("k", 1)
    message = "\n\n".join(request_data["messages"])

    echo_iterator = EchoAsyncIterator(message, k, delay=0.3)
    streamer = StreamingResponse(
        echo_iterator,
        media_type="text/event-stream",
    )

    return streamer
