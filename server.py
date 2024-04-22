import asyncio
import utils
import bittensor as bt
from aiohttp import web
from aiohttp.web_response import Response
from validators import S1ValidatorWrapper, QueryValidatorParams
from middlewares import api_key_middleware, json_parsing_middleware

"""
# test
```
curl -X POST http://0.0.0.0:10000/chat/ -H "api_key: hello" -d '{"k": 5, "timeout": 3, "roles": ["user"], "messages": ["hello world"]}'

curl -X POST http://0.0.0.0:10000/chat/ -H "api_key: hey-michal" -d '{"k": 5, "timeout": 3, "roles": ["user"], "messages": ["on what exact date did the 21st century begin?"]}'

# stream
curl --no-buffer -X POST http://129.146.127.82:10000/echo/ -H "api_key: hey-michal" -d '{"k": 3, "timeout": 0.2, "roles": ["user"], "messages": ["i need to tell you something important but first"]}'
```

TROUBLESHOOT
check if port is open
```
sudo ufw allow 10000/tcp
sudo ufw allow 10000/tcp
```
# run
```
EXPECTED_ACCESS_KEY="hey-michal" pm2 start app.py --interpreter python3 --name app -- --neuron.model_id mock --wallet.name sn1 --wallet.hotkey v1 --netuid 1 --neuron.tasks math --neuron.task_p 1 --neuron.device cpu
```

basic testing
```
EXPECTED_ACCESS_KEY="hey-michal" python app.py --neuron.model_id mock --wallet.name sn1 --wallet.hotkey v1 --netuid 1 --neuron.tasks math --neuron.task_p 1 --neuron.device cpu
```
add --mock to test the echo stream
"""

validator = None

@api_key_middleware
@json_parsing_middleware
async def chat(request: web.Request) -> Response:
    """
    Chat endpoint for the validator.
    """    
    request_data = request['data']
    params = QueryValidatorParams.from_dict(request_data)    
    # TODO: SET STREAM AS DEFAULT
    stream = request_data.get('stream', False)        
    response = await validator.query_validator(params, stream=stream)
    return response


@api_key_middleware
@json_parsing_middleware
async def echo_stream(request, request_data):    
    request_data = request['data']
    return await utils.echo_stream(request_data)

class ValidatorApplication(web.Application):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.middlewares.append(api_key_middleware)
        self.middlewares.append(json_parsing_middleware)

        # TODO: Enable rewarding and other features


validator_app = ValidatorApplication()
validator_app.add_routes([
    web.post('/chat/', chat),
    web.post('/echo/', echo_stream)
    ])

bt.logging.info("Starting validator application.")
bt.logging.info(validator_app)


def main(run_aio_app=True, test=False) -> None:
    loop = asyncio.get_event_loop()
    port = 10000
    if run_aio_app:
        try:
            web.run_app(validator_app, port=port, loop=loop)
        except KeyboardInterrupt:
            bt.logging.warning("Keyboard interrupt detected. Exiting validator.")
        finally:
            pass

if __name__ == "__main__":
    validator = S1ValidatorWrapper()
    main()
