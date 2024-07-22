from pydantic import BaseModel, Field
from typing import Optional, Literal, Any


class QueryChatRequest(BaseModel):
    k: Optional[int] = Field(
        default=1, description="The number of miners from which to request responses."
    )
    exclude: Optional[list[str]] = Field(
        None, description="A list of roles or agents to exclude from querying."
    )
    roles: list[str] = Field(..., description="The roles of the agents to query.")
    messages: list[str] = Field(
        ..., description="The messages to be sent to the network."
    )
    timeout: Optional[int] = Field(
        None, description="The time in seconds to wait for a response."
    )
    prefer: Optional[str] = Field(
        None,
        description="The preferred response format, can be either 'longest' or 'shortest'.",
    )
    sampling_mode: Optional[Literal["random", "top_incentive"]] = Field(
        "random",
        description="The mode of sampling to use, defaults to 'random'. Can be either 'random' or 'top_incentive'.",
    )
    request: Optional[Any]


class StreamChunkResponse(BaseModel):
    delta: str = Field(..., description="The new chunk of response received.")
    finish_reason: Optional[str] = Field(
        None, description="The reason for the response completion, if applicable."
    )
    accumulated_chunks: Optional[list[str]] = Field(
        None, description="All accumulated chunks of responses."
    )
    accumulated_chunks_timings: Optional[list[float]] = Field(
        None, description="Timing for each chunk received."
    )
    timestamp: str = Field(
        ..., description="The timestamp at which the chunk was processed."
    )
    sequence_number: int = Field(
        ..., description="A sequential identifier for the response part."
    )
    selected_uid: int = Field(
        ..., description="The identifier for the selected response source."
    )


class StreamErrorResponse(BaseModel):
    error: str = Field(..., description="Description of the error occurred.")
    timestamp: str = Field(..., description="The timestamp of the error.")
    sequence_number: int = Field(
        ..., description="A sequential identifier for the error."
    )
    finish_reason: Optional[str] = Field(
        "error", description="Indicates an error completion."
    )
