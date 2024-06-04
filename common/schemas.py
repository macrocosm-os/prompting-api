from marshmallow import Schema, fields


class QueryChatSchema(Schema):
    k = fields.Int(description="The number of miners from which to request responses.", default=10)
    exclude = fields.List(fields.Str(), description="A list of roles or agents to exclude from querying.")
    roles = fields.List(fields.Str(), required=True, description="The roles of the agents to query.")
    messages = fields.List(fields.Str(), required=True, description="The messages to be sent to the network.")
    timeout = fields.Int(description="The time in seconds to wait for a response.", default=10)
    prefer = fields.Str(description="The preferred response format, can be either 'longest' or 'shortest'.", default='longest')
    sampling_mode = fields.Str(
        description="The mode of sampling to use, defaults to 'random'. Can be either 'random' or 'top_incentive'.", default='top_incentive')


class StreamChunkSchema(Schema):
    delta = fields.Str(required=True, description="The new chunk of response received.")
    finish_reason = fields.Str(description="The reason for the response completion, if applicable.")
    accumulated_chunks = fields.List(fields.Str(), description="All accumulated chunks of responses.")
    accumulated_chunks_timings = fields.List(fields.Float(), description="Timing for each chunk received.")
    timestamp = fields.Str(required=True, description="The timestamp at which the chunk was processed.")
    sequence_number = fields.Int(required=True, description="A sequential identifier for the response part.")
    selected_uid = fields.Int(required=True, description="The identifier for the selected response source.")


class StreamErrorSchema(Schema):
    error = fields.Str(required=True, description="Description of the error occurred.")
    timestamp = fields.Str(required=True, description="The timestamp of the error.")
    sequence_number = fields.Int(required=True, description="A sequential identifier for the error.")
    finish_reason = fields.Str(default="error", description="Indicates an error completion.")
