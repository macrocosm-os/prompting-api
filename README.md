
<picture>
    <source srcset="./assets/macrocosmos-white.png"  media="(prefers-color-scheme: dark)">
    <img src="macrocosmos-white.png">
</picture>

<picture>
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
The API server is a RESTful API that provides endpoints for interacting with the network. It is a simple [wrapper](./validators/sn1_validator_wrapper.py) around your subnet 1 validator, which makes use of the dendrite to make queries.

## Install
Create a new python environment and install the dependencies with the command. 

(First time only)
```bash
python3.10 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

> Note:  This project requires python >=3.10.

> Note: Currently the prompting library is only installable on machines with cuda devices (NVIDIA-GPU).

## Run

First activate the virtual environment and then run the following command to start the server:

```bash
source env/bin/activate
```

Run an API server on subnet 1 with the following command:

```bash
EXPECTED_ACCESS_KEY=<ACCESS_KEY> python server.py --wallet.name <WALLET_NAME> --wallet.hotkey <WALLET_HOTKEY> --netuid <NETUID> --neuron.model_id mock --neuron.tasks math --neuron.task_p 1 --neuron.device cpu
```

The command ensures that no GPU memory is used by the server, and that the large models used by the incentive mechanism are not loaded.

> Note: This command is subject to change as the project evolves.

We recommend that you run the server using a process manager like PM2. This will ensure that the server is always running and will restart if it crashes. 

```bash
EXPECTED_ACCESS_KEY=<ACCESS_KEY> pm2 start server.py --interpreter python3 --name sn1-api -- --wallet.name <WALLET_NAME> --wallet.hotkey <WALLET_HOTKEY> --netuid <NETUID> --neuron.model_id mock --neuron.tasks math --neuron.task_p 1 --neuron.device cpu
```

## API Usage
At present, the API provides two endpoints: `/chat` (live) and `/echo` (test). 

`/chat` is used to chat with the network and receive a response. The endpoint requires a JSON payload with the following fields:
- `k: int`: The number of responses to return
- `timeout: float`: The time in seconds to wait for a response
- `roles: List[str]`: The roles of the agents to query
- `messages: List[str]`: The messages to send to the network
- `prefer: str`: The preferred response to use as the default view. Should be one of `{'longest', 'shortest'}`

Responses from the `/chat` endpoint are streamed back to the client as they are received from the network. Upon completion, the server will return a JSON response with the following fields:
- `streamed_chunks: List[str]`: The streamed responses from the network
- `streamed_chunks_timings: List[float]`: The time taken to receive each streamed response
- `synapse: StreamPromptingSynapse`: The synapse used to query the network. This contains full context and metadata about the query.


## Testing

To test the API locally, you can use the following curl command:

```bash
curl --no-buffer -X POST http://0.0.0.0:10000/chat/ -H "api_key: <ACCESS_KEY>" -d '{"k": 5, "timeout": 15, "roles": ["user"], "messages": ["What is today's date?"]}'
"""
```
> Note: Use the `--no-buffer` flag to ensure that the response is streamed back to the client.

After verifying that the server is responding to requests locally, you can test the server on a remote machine.

### Troubleshooting

If you do not receive a response from the server, check that the server is running and that the port is open on the server. You can open the port using the following commands:

```bash
sudo ufw allow 10000/tcp
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

