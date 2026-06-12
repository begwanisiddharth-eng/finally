"""LiteLLM -> Groq client with rate-limit backoff and structured output.

Follows the Groq skill: model lives under the openai/ namespace, reasoning_effort
must be allowlisted, and retries cover Groq rate limits / overloads.
"""

from __future__ import annotations

import litellm
from litellm import acompletion
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .schema import ChatResponse

MODEL = "groq/openai/gpt-oss-120b"


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=64),
    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError)),
)
async def completion_with_backoff(**kwargs):
    kwargs.setdefault("allowed_openai_params", ["reasoning_effort"])
    return await acompletion(**kwargs)


async def call_llm(messages: list[dict]) -> ChatResponse:
    """Call Groq with structured outputs and parse into a ChatResponse.

    Uses the async LiteLLM client so the network round-trip does not block the
    event loop (which would stall the SSE price stream for the whole process).
    """
    response = await completion_with_backoff(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="high",
    )
    content = response.choices[0].message.content
    return ChatResponse.model_validate_json(content)
