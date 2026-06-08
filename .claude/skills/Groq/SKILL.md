---
name: Groq Inference
description: Use this to write code to call an LLM using LiteLLM and the openai/gpt-oss-120b model with the Groq inference provider
---

# Calling an LLM via Groq

These instructions allow you write code to call an LLM with Groq specified as the inference provider.  
This method uses LiteLLM natively and includes error handling for Groq rate limits.

## Setup

The GROQ_API_KEY must be set in the .env file and loaded in as an environment variable.  

The uv project must include litellm, pydantic, and tenacity.
`uv add litellm pydantic tenacity`

## Rate Limit Handling (429 Errors)

Groq enforces strict tokens-per-minute (TPM) and requests-per-minute (RPM) limits. 
The cleanest way to handle these errors is combining LiteLLM's internal error types with the `tenacity` library for exponential backoff retries.

```python
import litellm
from litellm import completion
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Retry only on specific Groq rate limits or connection overloads
@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=64),
    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError))
)
def completion_with_backoff(**kwargs):
    # litellm does not yet recognize that Groq's gpt-oss models accept
    # `reasoning_effort`, so it must be allowlisted explicitly or the call
    # is rejected with UnsupportedParamsError before reaching Groq.
    kwargs.setdefault("allowed_openai_params", ["reasoning_effort"])
    return completion(**kwargs)
```

## Code snippets

Use code like these examples in order to use Groq securely.

### Imports and constants

```python
import litellm
from litellm import completion
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Note: the model lives under the `openai/` namespace on Groq, not bare `gpt-oss-120b`
MODEL = "groq/openai/gpt-oss-120b"

@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=64),
    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError))
)
def completion_with_backoff(**kwargs):
    kwargs.setdefault("allowed_openai_params", ["reasoning_effort"])
    return completion(**kwargs)
```

### Code to call via Groq for a text response

```python
response = completion_with_backoff(model=MODEL, messages=messages, reasoning_effort="high")
result = response.choices[0].message.content
```

### Code to call via Groq for a Structured Outputs response

```python
response = completion_with_backoff(model=MODEL, messages=messages, response_format=MyBaseModelSubclass, reasoning_effort="high")
result = response.choices[0].message.content
result_as_object = MyBaseModelSubclass.model_validate_json(result)
```