import asyncio
import os

import bittensor as bt
from aiohttp import web
from aiohttp_apispec import (
    docs,
    request_schema,
    response_schema,
    setup_aiohttp_apispec,
    validation_middleware,
)

from common import utils
from common.middlewares import api_key_middleware, json_parsing_middleware
from common.schemas import QueryChatSchema, StreamChunkSchema, StreamErrorSchema
from validators import QueryValidatorParams, S1ValidatorAPI, ValidatorAPI


@docs(tags=["Prompting API"], summary="Chat", description="Chat endpoint.")
@request_schema(QueryChatSchema)
@response_schema(StreamChunkSchema, 200)
@response_schema(StreamErrorSchema, 400)
async def chat(request: web.Request) -> web.StreamResponse:
    """Chat endpoint for the validator"""
    params = QueryValidatorParams.from_request(request)

    # Access the validator from the application context
    validator: ValidatorAPI = request.app["validator"]

    response = await validator.query_validator(params)
    return response


@docs(
    tags=["Prompting API"],
    summary="Echo test",
    description="Echo endpoint for testing purposes.",
)
@request_schema(QueryChatSchema)
@response_schema(StreamChunkSchema, 200)
@response_schema(StreamErrorSchema, 400)
async def echo_stream(request: web.Request) -> web.StreamResponse:
    return await utils.echo_stream(request)


class ValidatorApplication(web.Application):
    def __init__(self, validator_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self["validator"] = (
            validator_instance if validator_instance else S1ValidatorAPI(query_validators=True)
        )

        # Add middlewares to application
        self.add_routes(
            [
                web.post("/chat/", chat),
                web.post("/echo/", echo_stream),
            ]
        )
        self.setup_openapi()
        self.setup_middlewares()
        # TODO: Enable rewarding and other features

    def setup_middlewares(self):
        self.middlewares.append(validation_middleware)
        self.middlewares.append(json_parsing_middleware)
        self.middlewares.append(api_key_middleware)

    def setup_openapi(self):
        setup_aiohttp_apispec(
            app=self,
            title="Prompting API",
            url="/docs/swagger.json",
            swagger_path="/docs",
        )


def main(run_aio_app=True, test=False) -> None:
    loop = asyncio.get_event_loop()
    port = os.environ.get("PORT", 42177)
    if run_aio_app:
        # Instantiate the application with the actual validator
        bt.logging.info("Starting validator application.")
        validator_app = ValidatorApplication()
        bt.logging.success("Validator app initialized successfully", validator_app)

        try:
            web.run_app(validator_app, port=port, loop=loop)
        except KeyboardInterrupt:
            print("Keyboard interrupt detected. Exiting validator.")
        finally:
            pass


if __name__ == "__main__":
    main()
