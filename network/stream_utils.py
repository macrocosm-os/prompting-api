import json
from pydantic import BaseModel
from typing import Optional, List


class StreamChunk(BaseModel):
    delta: str
    finish_reason: Optional[str]
    accumulated_chunks: List[str]
    accumulated_timings: List[float]
    timestamp: str
    sequence_number: int
    miner_uid: int
    validator_uid: int

    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)


class StreamError(BaseModel):
    error: str
    timestamp: str
    sequence_number: int
    finish_reason: str = "error"

    def encode(self, encoding: str) -> bytes:
        data = json.dumps(self.dict(), indent=4)
        return data.encode(encoding)
