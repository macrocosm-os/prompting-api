import asyncio
import utils
import bittensor as bt
from aiohttp import web
from validators import S1ValidatorAPI, QueryValidatorParams, ValidatorAPI
from middlewares import api_key_middleware, json_parsing_middleware


async def chat(request: web.Request) -> web.StreamResponse:
    """
    Chat endpoint for the validator.
    """
    params = QueryValidatorParams.from_request(request)

    # Access the validator from the application context
    validator: ValidatorAPI = request.app["validator"]

    response = await validator.query_validator(params)
    return response


async def echo_stream(request: web.Request) -> web.StreamResponse:
    return await utils.echo_stream(request)


class ValidatorApplication(web.Application):
    def __init__(self, validator_instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self["validator"] = (
            validator_instance if validator_instance else S1ValidatorAPI()
        )

        # Add middlewares to application
        self.add_routes([web.post("/chat/", chat), web.post("/echo/", echo_stream)])
        self.setup_middlewares()
        # TODO: Enable rewarding and other features

    def setup_middlewares(self):
        self.middlewares.append(json_parsing_middleware)
        self.middlewares.append(api_key_middleware)


def main(run_aio_app=True, test=False) -> None:
    loop = asyncio.get_event_loop()
    port = 10000
    if run_aio_app:
        # Instantiate the application with the actual validator
        bt.logging.info("Starting validator application.")
        validator_app = ValidatorApplication()
        bt.logging.success(f"Validator app initialized successfully", validator_app)

        try:
            web.run_app(validator_app, port=port, loop=loop)
        except KeyboardInterrupt:
            print("Keyboard interrupt detected. Exiting validator.")
        finally:
            pass


if __name__ == "__main__":
    main()
