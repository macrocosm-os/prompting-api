from pydantic import BaseModel, Field
from typing import List, Dict, Any

class TextStreamResponse(BaseModel):
    streamed_chunks: List[str] = Field(default_factory=list, description="List of streamed chunks.")
    streamed_chunks_timings: List[float] = Field(default_factory=list, description="List of streamed chunks timings, in seconds.")
    uid: int = Field(0, description="UID of queried miner")
    completion: str = Field('', description="The final completed string from the stream.")
    timing: float = Field(0, description="Timing information of all request, in seconds.")    

    def to_dict(self):
        return {
            "streamed_chunks": self.streamed_chunks,
            "streamed_chunks_timings": self.streamed_chunks_timings,
            "uid": self.uid,
            "completion": self.completion,
            "timing": self.timing
        }