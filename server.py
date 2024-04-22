


import os
import time
import asyncio
import json
import bittensor as bt
from collections import Counter
from validator_wrapper import QueryValidatorParams, S1ValidatorWrapper
from prompting.rewards import DateRewardModel, FloatDiffModel
from aiohttp import web
from aiohttp.web_response import Response

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

EXPECTED_ACCESS_KEY = os.environ.get('EXPECTED_ACCESS_KEY')

validator = None


async def chat(request: web.Request) -> Response:
    """
    Chat endpoint for the validator.

    Required headers:
    - api_key: The access key for the validator.

    Required body:
    - roles: The list of roles to query.
    - messages: The list of messages to query.
    Optional body:
    - k: The number of nodes to query.
    - exclude: The list of nodes to exclude from the query.
    - timeout: The timeout for the query.
    """

    bt.logging.info(f'chat()')
    # Check access key
    access_key = request.headers.get("api_key")
    if EXPECTED_ACCESS_KEY is not None and access_key != EXPECTED_ACCESS_KEY:
        bt.logging.error(f'Invalid access key: {access_key}')
        return Response(status=401, reason="Invalid access key")

    try:
        request_data = await request.json()
    except ValueError:
        bt.logging.error(f'Invalid request data: {request_data}')
        return Response(status=400)
        
    # try:
    #     # Guess the task name of current request
    #     task_name = guess_task_name(request_data['messages'][-1])
                        
    #     # Get the list of uids to query for this step.
    #     params = QueryValidatorParams.from_dict(request_data)
    #     response_event = await validator.query_validator(params)        
                
    #     # convert dict to json
    #     response = response_event.__state_dict__()
        
    #     response['completion_is_valid'] = valid = list(map(completion_is_valid, response['completions']))
    #     valid_completions = [response['completions'][i] for i, v in enumerate(valid) if v]

    #     response['task_name'] = task_name
    #     prefer = request_data.get('prefer', 'longest')
    #     response['ensemble_result'] = ensemble_result(valid_completions, task_name=task_name, prefer=prefer)
        
    #     bt.logging.info(f"Response:\n {response}")
    #     return Response(status=200, reason="I can't believe it's not butter!", text=json.dumps(response))
    # except Exception:
    #     bt.logging.error(f'Encountered in {chat.__name__}:\n{traceback.format_exc()}')
    #     return Response(status=500, reason="Internal error")
    bt.logging.info(f'Request data: {request_data}')

    stream = request_data.get('stream', False)
    if stream:
        return stream_response(**request_data)
    else:
        return single_response(**request_data)




async def echo_stream(request):

    bt.logging.info(f'echo_stream()')
    # Check access key
    access_key = request.headers.get("api_key")
    if EXPECTED_ACCESS_KEY is not None and access_key != EXPECTED_ACCESS_KEY:
        bt.logging.error(f'Invalid access key: {access_key}')
        return Response(status=401, reason="Invalid access key")

    try:
        request_data = await request.json()
    except ValueError:
        bt.logging.error(f'Invalid request data: {request_data}')
        return Response(status=400)

    bt.logging.info(f'Request data: {request_data}')
    k = request_data.get('k', 1)
    exclude = request_data.get('exclude', [])
    timeout = request_data.get('timeout', 0.2)
    message = '\n\n'.join(request_data['messages'])

    # Create a StreamResponse
    response = web.StreamResponse(status=200, reason='OK', headers={'Content-Type': 'text/plain'})
    await response.prepare(request)

    completion = ''
    # Echo the message k times with a timeout between each chunk
    for _ in range(k):
        for word in message.split():
            chunk = f'{word} '
            await response.write(chunk.encode('utf-8'))
            completion += chunk
            time.sleep(timeout)
            bt.logging.info(f"Echoed: {chunk}")

    completion = completion.strip()

    # Prepare final JSON chunk
    json_chunk = json.dumps({
        "uids": [0],
        "completion": completion,
        "completions": [completion.strip()],
        "timings": [0],
        "status_messages": ['Went well!'],
        "status_codes": [200],
        "completion_is_valid": [True],
        "task_name": 'echo',
        "ensemble_result": {}
    })

    # Send the final JSON as part of the stream
    await response.write(f"\n\nJSON_RESPONSE_BEGIN:\n{json_chunk}".encode('utf-8'))

    # Finalize the response
    await response.write_eof()
    return response


class ValidatorApplication(web.Application):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
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
