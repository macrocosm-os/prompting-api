import bittensor as bt
from neurons.validator import Validator
from prompting.utils.uids import get_random_uids
from prompting.protocol import PromptingSynapse
from prompting.dendrite import DendriteResponseEvent
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class QueryValidatorParams:
    k_miners: int
    exclude: List[str]
    roles: List[str]
    messages: List[str]
    timeout: int
    
    @staticmethod
    def from_dict(data: dict):
        return QueryValidatorParams(            
            k_miners=data.get('k', 10),
            exclude=data.get('exclude', []),
            roles=data['roles'],
            messages=data['messages'],
            timeout=data.get('timeout', 10)
        )

class ValidatorWrapper(ABC):
    @abstractmethod
    async def query_validator(self, params:QueryValidatorParams):
        pass
    
    
class S1ValidatorWrapper(ValidatorWrapper):
    def __init__(self):
        self.validator = Validator()    
    
    async def query_validator(self, params:QueryValidatorParams) -> DendriteResponseEvent:
        # Get the list of uids to query for this step.
        uids = get_random_uids(
            self.validator,
            k=params.k_miners,
            exclude=params.exclude).to(self.validator.device)
        
        axons = [self.validator.metagraph.axons[uid] for uid in uids]

        # Make calls to the network with the prompt.
        bt.logging.info(f'Calling dendrite')
        responses = await self.validator.dendrite(
            axons=axons,
            synapse=PromptingSynapse(roles=params.roles, messages=params.request_data.messages),
            timeout=params.timeout,
        )
        
        # Encapsulate the responses in a response event (dataclass)
        bt.logging.info(f"Creating DendriteResponseEvent:\n {responses}")
        response_event = DendriteResponseEvent(responses, uids)
        return response_event
        
    
class MockValidator(ValidatorWrapper):
    def query_validator(self, query: str) -> bool:
        return False




