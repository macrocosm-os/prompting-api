from pydantic import BaseModel, Field
from typing import Optional, Literal, Any
import json


class QueryChatRequest(BaseModel):
    k: Optional[int] = Field(
        default=1,
        description="The number of miners or validators from which to request responses.",
    )
    excluded_uids: Optional[list[str]] = Field(None, description="A list of UIDs to exclude from querying.")
    roles: list[str] = Field(..., description="The roles of the agents to query.")
    messages: list[str] = Field(..., description="The messages to be sent to the network.")
    timeout: Optional[int] = Field(5, description="The time in seconds to wait for a response.")
    query_validators: Optional[bool] = Field(True, description="Whether to query validators.")
    sampling_mode: Literal["random", "list", "top_incentive"] = Field(
        "list", description="The mode of sampling the miners."
    )
    validator_min_staked_tao: Optional[int] = Field(4096, description="The minimum tao for a validator to be queried.")
    uid_list: Optional[list[int]] = Field([5], description="List of uids to sample from, if sampling_mode is 'list'.")
    request: Optional[Any]


class StreamChunk(BaseModel):
    delta: str = Field(..., description="The new chunk of response received.")
    finish_reason: Optional[str] = Field(None, description="The reason for the response completion, if applicable.")
    accumulated_chunks: list[str] = Field(None, description="All accumulated chunks of responses.")
    accumulated_timings: list[float] = Field(None, description="Timing for each chunk received.")
    timestamp: str = Field(..., description="The timestamp at which the chunk was processed.")
    sequence_number: int = Field(..., description="A sequential identifier for the response part.")
    miner_uid: int = Field(..., description="The miner identifier for the selected response source.")
    validator_uid: int = Field(..., description="The validator identifier for the selected response source.")

    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)


class StreamError(BaseModel):
    error: str = Field(..., description="Description of the error occurred.")
    timestamp: str = Field(..., description="The timestamp of the error.")
    sequence_number: int = Field(..., description="A sequential identifier for the error.")
    finish_reason: Optional[str] = Field("error", description="Indicates an error completion.")
    miner_uid: int = Field(..., description="The miner identifier for the selected response source.")
    validator_uid: int = Field(..., description="The validator identifier for the selected response source.")

    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)
