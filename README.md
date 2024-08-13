
<picture>
    <source srcset="./assets/macrocosmos-white.png"  media="(prefers-color-scheme: dark)">
    <source srcset="./assets/macrocosmos-black.png"  media="(prefers-color-scheme: light)">
    <img src="macrocosmos-black.png">
</picture>

<br/>
<br/>
<br/>

# Subnet 1 API
> Note: This project is still in development and is not yet ready for production use.

The official REST API for Bittensor's flagship subnet 1 ([prompting](https://github.com/opentensor/prompting)), built by [Macrocosmos](https://macrocosmos.ai).

Subnet 1 is an decentralized open source network containing around 1000 highly capable LLM agents. These agents are capable of performing a wide range of tasks, from simple math problems to complex natural language processing tasks. As subnet 1 is constantly evolving, its capabilities are always expanding. Our goal is to provide a world-class inference engine, to be used by developers and researchers alike.

This API is designed to power applications and facilitate the interaction between subnets by providing a simple and easy-to-use interface for developers which enables:
1. **Conversation**: Chatting with the network (streaming and non-streaming)
2. **Data cleaning**: Filtering empty and otherwise useless responses
3. **Advanced inference**: Providing enhanced responses using SOTA ensembling techniques (WIP)

Validators can use this API to interact with the network and perform various tasks.
To run an API server, you will need a bittensor wallet which is registered as a validator the relevant subnet (1@mainnet or 61@testnet).

NOTE: At present, miners are choosing not to stream their responses to the network. This means that the server will not be able to provide a streamed response to the client until the miner has finished processing the request. This is a temporary measure and will be resolved in the future.

## How it works
The API server is a RESTful API (written using FastAPI) that provides endpoints for interacting with the network. It uses your wallet to create a *validator-like* object called a [`Neuron`](.network/neuron.py) to access the network by making use of a dendrite to make queries.

## Install

Run:
```sh
poetry install
```
to install all packages

## Run

First activate the virtual environment:

```bash
poetry shell
```

Then, set up your `.env` file by copying `.env.example` and going through each setting including setting an API key (which is optional).

### Running On SN1

Run an API server on subnet 61 (test subnet) with the following command:

```bash
python api.py
```

Environment variables (`.env`):

- `EXPECTED_ACCESS_KEY`: API access key
- `COLDKEY_WALLET_NAME`: The coldkey wallet name
- `HOTKEY_WALLET_NAME`: The hotkey wallet name linked to the cold key
- `WALLET_PATH`: The path to the bittensor wallet
- `SUBTENSOR_NETWORK`: The bittensor network name (`finney` (main) or `test` or `local` - Default: `finney`)
- `NETUID`: The bittensor network UID (for SN1, this should be `1` - Default: `1`)
- `QUERY_UNIQUE_COLDKEYS`: When querying multiple miners, we will query unique coldkeys only once (Default: `false`)
- `QUERY_UNIQUE_IPS`: When querying multiple miners, we will query unique IPs only once (Default: `false`)
- `QUERY_VALIDATOR_PORT`: When querying validators, we will use this port number
- `VALIDATOR_MIN_STAKE`: The minimal TAO staked on a UID to be considered a validator
- `RESYNC_METAGRAPH_INTERVAL`: The interval in seconds on how often the API refreshes its metagraph (updates UID statuses)

> Note: This command is subject to change as the project evolves.

We recommend that you run the server using a process manager like PM2. This will ensure that the server is always running and will restart if it crashes.

```bash
pm2 start api.py --interpreter python3 --name sn1-api
```

### Run with Docker (WARNING: not tested)

To run api in docker container you have to build the image:
```
docker build . -t prompting-api
```
after the image is build properly
you can start it with command:

```
docker run -e prompting-api:latest --interpreter python3 --name sn1-api
```

## Testing the API

Once you've started the API server, you can use Swagger UI to test the API by going to [http://localhost:8000/docs](http://localhost:8000/docs)

## API Usage
At present, the API provides two endpoints: `/chat` (live) and `/echo` (test).

`/chat` is used to chat with the network and receives a streamed response. It requires a JSON payload structured as per the QueryValidatorParams class.
The request payload requires the following parameters encapsulated within the [`QueryChatRequest`](./network/meta/schemas.py) data class:
- `k: int`: The number of miners from which to request responses.
- `excluded_uids: list[int]`: A list of UIDs to exclude from querying.
- `roles: List[str]`: The roles of the agents to query. (e.g. `["user"]`).
- `messages: List[str]`: The messages to be sent to the network (e.g. `["as above, so below"]`).
- `timeout: int`: The time in seconds to wait for a response.
- `query_validators: bool`: Whether to query validators (`true` = validators (default) | `false` = miners).
- `sampling_mode: str`: The mode of sampling to use, defaults to `list`. Can be either `list` (default), `random`, or `top_incentive` (Note: `top_incentive` is only for when querying miners directly - `query_validators = "false"`).
- `uid_list: List[int]`: When sampling_mode = `list`, this must contain the list of UIDs that will be considered (Default: `5` the opentensor validator UID).

Responses from the `/chat` endpoint are handled by two classes: `StreamChunk` and `StreamError`, with their attributes defined as follows:
- `StreamChunk`:
  - `delta: str`: The new chunk of response received.
  - `finish_reason: Optional[str]`: The reason for the response completion, if applicable Can be `None` or `completed` (Note: A `completed` chunk will still be sent when a `StreamError` occurs).
  - `accumulated_chunks: List[str]`: All chunks of responses accumulated thus far.
  - `accumulated_timings: List[float]`: Timing for each chunk received.
  - `timestamp: str`: The timestamp at which the chunk was processed.
  - `sequence_number: int`: A sequential identifier for the response part (for the `finish_reason = "completed"`, this will be `-1`).
  - `miner_uid: int`: The miner identifier for the response source (if not known or does not apply, this will be `-1`).
  - `validator_uid: int`: The validator identifier for the response source (if querying miners, this will be `-1`).

- `StreamError`:
  - `error: str`: Description of the error occurred.
  - `timestamp: str`: The timestamp of the error.
  - `sequence_number: int`: A sequential identifier for the error.
  - `finish_reason: str`: Always set to `'error'` to indicate an error completion.
  - `miner_uid: int`: The miner identifier for the response source (if not known or does not apply, this will be `-1`).
  - `validator_uid: int`: The validator identifier for the response source (if not known or when querying miners, this will be `-1`).

> Note: The API is subject to change as the project evolves.

## Testing Locally
To test the API locally, you can use the following curl command:

```bash
curl -X 'POST' \
  'http://localhost:8000/chat/' \
  -H 'accept: application/json' \
  -H 'api_key: <<API_KEY>>' \
  -H 'Content-Type: application/json' \
  -d '{
  "k": 1,
  "excluded_uids": [
    0
  ],
  "roles": [
    "user"
  ],
  "messages": [
    "as above, so below"
  ],
  "timeout": 5,
  "query_validators": true,
  "sampling_mode": "list",
  "uid_list": [
    5
  ]
}'
```

> Note: Use the `--no-buffer` flag to ensure that the response is streamed back to the client.

The above example prompt yields the following streamed response (each JSON object being a chunk):

```json
{
    "delta": "As above, so below\" is a found-footage horror film set in the catacombs of paris. The story follows jeff and steph, two young filmmakers who use their equipment to explore the catacombs, searching for their missing friend ben, who has been obsessed with the site. During their journey, they uncover a dark conspiracy involving a secret society that worships an ancient deity, known as \"the keeper,\" w",
    "finish_reason": null,
    "accumulated_chunks": [
        "As above, so below\" is a found-footage horror film set in the catacombs of paris. The story follows jeff and steph, two young filmmakers who use their equipment to explore the catacombs, searching for their missing friend ben, who has been obsessed with the site. During their journey, they uncover a dark conspiracy involving a secret society that worships an ancient deity, known as \"the keeper,\" w"
    ],
    "accumulated_timings": [
        1.77962112496607
    ],
    "timestamp": "2024-08-13T12:51:16.732858+00:00",
    "sequence_number": 1,
    "miner_uid": 527,
    "validator_uid": 5
}{
    "delta": "ho is said to reside in the catacombs. The film is directed by john erick dowdle and written by edward r. Pressman.",
    "finish_reason": null,
    "accumulated_chunks": [
        "As above, so below\" is a found-footage horror film set in the catacombs of paris. The story follows jeff and steph, two young filmmakers who use their equipment to explore the catacombs, searching for their missing friend ben, who has been obsessed with the site. During their journey, they uncover a dark conspiracy involving a secret society that worships an ancient deity, known as \"the keeper,\" w",
        "ho is said to reside in the catacombs. The film is directed by john erick dowdle and written by edward r. Pressman."
    ],
    "accumulated_timings": [
        1.77962112496607,
        2.572092041024007
    ],
    "timestamp": "2024-08-13T12:51:17.525321+00:00",
    "sequence_number": 2,
    "miner_uid": 527,
    "validator_uid": 5
}{
    "delta": "",
    "finish_reason": "completed",
    "accumulated_chunks": [],
    "accumulated_timings": [
        3.2269902910338715
    ],
    "timestamp": "2024-08-13T12:51:18.180205+00:00",
    "sequence_number": -1,
    "miner_uid": -1,
    "validator_uid": 5
}
```
After verifying that the server is responding to requests locally, you can test the server on a remote machine.

### Troubleshooting

If you do not receive a response from the server, check that the server is running and that the port is open on the server. You can open the port using the following commands:

```bash
sudo ufw allow 8000/tcp
```

---

## Contributing
If you would like to contribute to the project, please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for more information.

You can find out more about the project by visiting the [Macrocosmos website](https://macrocosmos.ai) or by joining us in our social channels:


![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
[![Substack](https://img.shields.io/badge/Substack-%23006f5c.svg?style=for-the-badge&logo=substack&logoColor=FF6719)](https://substack.com/@macrocosmosai)
[![Twitter](https://img.shields.io/badge/Twitter-%231DA1F2.svg?style=for-the-badge&logo=twitter&logoColor=white)](https://twitter.com/MacrocosmosAI)
[![X](https://img.shields.io/badge/X-%23000000.svg?style=for-the-badge&logo=X&logoColor=white)](https://twitter.com/MacrocosmosAI)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?logo=linkedin&logoColor=white)](www.linkedin.com/in/MacrocosmosAI)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
