from dotenv import load_dotenv
from loguru import logger
import os

# We clear the environment to avoid any conflicts with changes in the .env file.
os.environ.clear()

if not load_dotenv():
    logger.warning("No .env file found, test endpoint will not be functional...")

# The API key others will use to access this service
EXPECTED_ACCESS_KEY = os.getenv("EXPECTED_ACCESS_KEY")

############################
# API's wallet information #
############################

# The cold and hot key wallet names used by this service to access the bittensor network.
COLDKEY_WALLET_NAME = os.environ.get("COLDKEY_WALLET_NAME")
HOTKEY_WALLET_NAME = os.environ.get("HOTKEY_WALLET_NAME")

# Leave the WALLET_PATH as None to use the default wallet path.
WALLET_PATH = os.environ.get("WALLET_PATH")

##########################
# Which network to query #
##########################

# The subtensor network to connect to.
#  None or finney = the main (prod) network
#  test = testnet
#  local = your own local network
SUBTENSOR_NETWORK = os.getenv("SUBTENSOR_NETWORK")

# The subnet UID to connect to.
#  1 = Subnet 1
#  61 = Subnet 1 on testnet
NETUID = int(os.environ.get("NETUID", 1))

############################
# How to query the network #
############################

# Make sure we look at unique cold keys
QUERY_UNIQUE_COLDKEYS = bool(os.environ.get("QUERY_UNIQUE_COLDKEYS", "false") == "true")

# Make sure we look at unique IPs
QUERY_UNIQUE_IPS = bool(os.environ.get("QUERY_UNIQUE_IPS", "false") == "true")

# Validator port to query (used if multiple validators are running on the same uid and we need to specify which port)
# e.g. OTF has two validators running on SN1 with the same hotkey
QUERY_VALIDATOR_PORT = os.environ.get("QUERY_VALIDATOR_PORT")
