import re
import asyncio

# import bittensor as bt
from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio
from collections import Counter

# from prompting.rewards import DateRewardModel, FloatDiffModel
from validators.streamer import AsyncResponseDataStreamer
from loguru import logger

shared_lock = asyncio.Lock()

UNSUCCESSFUL_RESPONSE_PATTERNS = [
    "I'm sorry",
    "unable to",
    "I cannot",
    "I can't",
    "I am unable",
    "I am sorry",
    "I can not",
    "don't know",
    "not sure",
    "don't understand",
    "not capable",
]

# reward_models = {
#     "date_qa": DateRewardModel(),
#     "math": FloatDiffModel(),
# }


def completion_is_valid(completion: str):
    """
    Get the completion statuses from the completions.
    """
    if not completion.strip():
        return False

    patt = re.compile(r"\b(?:" + "|".join(UNSUCCESSFUL_RESPONSE_PATTERNS) + r")\b", re.IGNORECASE)
    if not len(re.findall(r"\w+", completion)) or patt.search(completion):
        return False
    return True


# def ensemble_result(completions: list, task_name: str, prefer: str = "longest"):
#     """
#     Ensemble completions from multiple models.
#     # TODO: Measure agreement
#     # TODO: Figure out how to mitigate the cabal effect (large groups will appear to be more credible)
#     # TODO: Reward pipeline
#     """
#     if not completions:
#         return None

#     answer = None
#     if task_name in ("qa", "summarization"):
#         # No special handling for QA or summarization
#         supporting_completions = completions

#     elif task_name == "date_qa":
#         # filter the completions to be the ones that contain valid dates and if there are multiple dates, select the most common one (with support > 1)
#         dates = list(map(reward_models[task_name].parse_dates_from_text, completions))
#         bt.logging.info(f"Unprocessed dates: {dates}")
#         valid_date_indices = [i for i, d in enumerate(dates) if d]
#         valid_completions = [completions[i] for i in valid_date_indices]
#         valid_dates = [dates[i] for i in valid_date_indices]
#         dates = [f"{d[0].strftime('%-d %B')} {d[1]}" for d in valid_dates]
#         if not dates:
#             return None

#         counter = Counter(dates)
#         most_common, count = counter.most_common()[0]
#         answer = most_common
#         if count == 1:
#             supporting_completions = valid_completions
#         else:
#             supporting_completions = [
#                 c for i, c in enumerate(valid_completions) if dates[i] == most_common
#             ]

#     elif task_name == "math":
#         # filter the completions to be the ones that contain valid numbers and if there are multiple values, select the most common one (with support > 1)
#         # TODO: use the median instead of the most common value
#         vals = list(map(reward_models[task_name].extract_number, completions))
#         vals = [val for val in vals if val]
#         if not vals:
#             return None

#         most_common, count = Counter(dates).most_common()[0]
#         bt.logging.info(f"Most common value: {most_common}, count: {count}")
#         answer = most_common
#         if count == 1:
#             supporting_completions = completions
#         else:
#             supporting_completions = [
#                 c for i, c in enumerate(completions) if vals[i] == most_common
#             ]

#     bt.logging.info(f"Supporting completions: {supporting_completions}")
#     if prefer == "longest":
#         preferred_completion = sorted(supporting_completions, key=len)[-1]
#     elif prefer == "shortest":
#         preferred_completion = sorted(supporting_completions, key=len)[0]
#     elif prefer == "most_common":
#         preferred_completion = max(
#             set(supporting_completions), key=supporting_completions.count
#         )
#     else:
#         raise ValueError(f"Unknown ensemble preference: {prefer}")

#     return {
#         "completion": preferred_completion,
#         "accepted_answer": answer,
#         "support": len(supporting_completions),
#         "support_indices": [completions.index(c) for c in supporting_completions],
#         "method": f'Selected the {prefer.replace("_", " ")} completion',
#     }


def guess_task_name(challenge: str):
    # TODO: use a pre-trained classifier to guess the task name
    categories = {
        "summarization": re.compile("summar|quick rundown|overview"),
        "date_qa": re.compile("exact date|tell me when|on what date|on what day|was born?|died?"),
        "math": re.compile("math|solve|solution| sum |problem|geometric|vector|calculate|degrees|decimal|factorial"),
    }
    for task_name, patt in categories.items():
        if patt.search(challenge):
            return task_name

    return "qa"


# Simulate the stream synapse for the echo endpoint
class EchoAsyncIterator:
    def __init__(self, message: str, k: int, delay: float):
        self.message = message
        self.k = k
        self.delay = delay

    async def __aiter__(self):
        for _ in range(self.k):
            for word in self.message.split():
                yield [word]
                await asyncio.sleep(self.delay)


async def echo_stream(request: Request) -> StreamingResponse:
    request_data = await request.json()
    k = request_data.get("k", 1)
    message = "\n\n".join(request_data["messages"])

    echo_iterator = EchoAsyncIterator(message, k, delay=0.3)
    streamer = AsyncResponseDataStreamer(echo_iterator, selected_uid=0, lock=shared_lock, delay=0.3)

    return await streamer.stream(request)
