from dotenv import load_dotenv
from loguru import logger
import os

if not load_dotenv():
    logger.warning("No .env file found, test endpoint will not be functional...")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
