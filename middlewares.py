import os
import json
import bittensor as bt
from aiohttp.web import Response

EXPECTED_ACCESS_KEY = os.environ.get('EXPECTED_ACCESS_KEY')

async def api_key_middleware(app, handler):
    async def middleware_handler(request):
        # Logging the request
        bt.logging.info(f"Handling {request.method} request to {request.path}")

        # Check access key
        access_key = request.headers.get("api_key")
        if EXPECTED_ACCESS_KEY is not None and access_key != EXPECTED_ACCESS_KEY:
            bt.logging.error(f'Invalid access key: {access_key}')
            return Response(status=401, reason="Invalid access key")

        # Continue to the next handler if the API key is valid
        return await handler(request)
    return middleware_handler

async def json_parsing_middleware(app, handler):
    async def middleware_handler(request):
        try:
            # Parsing JSON data from the request
            request['data'] = await request.json()
        except json.JSONDecodeError as e:
            bt.logging.error(f'Invalid JSON data: {str(e)}')
            return Response(status=400, text="Invalid JSON")

        # Continue to the next handler if JSON is successfully parsed
        return await handler(request)
    return middleware_handler