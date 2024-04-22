from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
from aiohttp.web_response import Response

@dataclass
class QueryValidatorParams:
    k_miners: int
    exclude: List[str]
    roles: List[str]
    messages: List[str]
    timeout: int
    prefer: str
    
    @staticmethod
    def from_dict(data: dict):
        return QueryValidatorParams(            
            k_miners=data.get('k', 10),
            exclude=data.get('exclude', []),
            roles=data['roles'],
            messages=data['messages'],
            timeout=data.get('timeout', 10),
            prefer=data.get('prefer', 'longest')
        )

class ValidatorAPI(ABC):
    @abstractmethod
    async def query_validator(self, params:QueryValidatorParams) -> Response:
        pass
    
    
class MockValidator(ValidatorAPI):    
    async def query_validator(self, params:QueryValidatorParams) -> Response:
        ...
        