from fastapi import Request, Response
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import settings
from loguru import logger


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"Request: {request.url.path}")
        access_key = request.headers.get("api_key")

        if (
            request.url.path.startswith("/docs")
            or request.url.path.startswith("/openapi.json")
            or request.url.path.startswith("/static/swagger")
        ):
            # Skip checks when accessing OpenAPI documentation.
            return await call_next(request)
        # Check access key
        elif (
            settings.EXPECTED_ACCESS_KEY is not None
            and access_key != settings.EXPECTED_ACCESS_KEY
        ):
            logger.error(f"Invalid access key: {access_key}")
            return Response(
                status_code=401, content="Please provide a valid access key"
            )

        # Continue to the next handler if the API key is valid
        response = await call_next(request)
        return response


middleware = [Middleware(APIKeyMiddleware)]


# @middleware
# async def json_parsing_middleware(request: Request, handler):
#     if request.path.startswith("/docs") or request.path.startswith("/static/swagger"):
#         # Skip checks when accessing OpenAPI documentation.
#         return await handler(request)

#     try:
#         # Parsing JSON data from the request
#         request["data"] = await request.json()
#     except json.JSONDecodeError as e:
#         bt.logging.error(f"Invalid JSON data: {str(e)}")
#         return Response(status=400, text="Invalid JSON")

#     # Continue to the next handler if JSON is successfully parsed
#     return await handler(request)
