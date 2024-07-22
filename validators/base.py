from abc import ABC, abstractmethod
from aiohttp.web import StreamResponse
from common.schemas import QueryChatRequest

# @dataclass
# class QueryValidatorParams:
#     k_miners: int
#     exclude: List[str]
#     roles: List[str]
#     messages: List[str]
#     timeout: int
#     prefer: str
#     request: Request
#     sampling_mode: str

#     @staticmethod
#     def from_request(request: Request):
#         logger.info(f"Request: {request}")
#         data = request["data"]

#         return QueryValidatorParams(
#             k_miners=data.get("k", 10),
#             exclude=data.get("exclude", []),
#             roles=data["roles"],
#             messages=data["messages"],
#             timeout=data.get("timeout", 10),
#             prefer=data.get("prefer", "longest"),
#             request=request,
#             sampling_mode=data.get("sampling_mode", "random"),
#         )


class ValidatorAPI(ABC):
    @abstractmethod
    async def query_validator(self, params: QueryChatRequest) -> StreamResponse:
        pass


class OpenAIValidatorAPI(ValidatorAPI):
    async def query_validator(self, params: QueryChatRequest) -> StreamResponse:
        ...


class MockValidator(ValidatorAPI):
    async def query_validator(self, params: QueryChatRequest) -> StreamResponse:
        ...
