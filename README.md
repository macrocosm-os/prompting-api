# chattensor-backend
Backend for Chattensor app

To run, you will need a bittensor wallet which is registered to the relevant subnet (1@mainnet or 61@testnet).




## Install
Create a new python environment and install the dependencies with the command. **Note**: This project uses python >=3.10.

(First time only)
```bash
pip install -r requirements.txt
```

> Note: Currently the prompting library is only installable on machines with cuda devices (NVIDIA-GPU).

## Run

First activate the virtual environment and then run the following command to start the server.

```bash
source env/bin/activate
```

Run the server with the following command.

```bash
EXPECTED_ACCESS_KEY="macrocosmos" python server.py --neuron.model_id mock --wallet.name sn1 --wallet.hotkey v1 --netuid 1 --neuron.tasks math --neuron.task_p 1 --neuron.device cpu
```
Note that this command is subject to change as the project evolves.
