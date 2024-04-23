from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
from aiohttp.web import Response, Request


@dataclass
class QueryValidatorParams:
    k_miners: int
    exclude: List[str]
    roles: List[str]
    messages: List[str]
    timeout: int
    prefer: str
    request: Request

    @staticmethod
    def from_request(request: Request):
        data = request["data"]

        return QueryValidatorParams(
            k_miners=data.get("k", 10),
            exclude=data.get("exclude", []),
            roles=data["roles"],
            messages=data["messages"],
            timeout=data.get("timeout", 10),
            prefer=data.get("prefer", "longest"),
            request=request,
        )


class ValidatorAPI(ABC):
    @abstractmethod
    async def query_validator(self, params: QueryValidatorParams) -> Response:
        pass


class MockValidator(ValidatorAPI):
    async def query_validator(self, params: QueryValidatorParams) -> Response:
        ...
