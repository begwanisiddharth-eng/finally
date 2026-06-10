1	---
2	name: Groq Inference
3	description: Use this to write code to call an LLM using LiteLLM and the openai/gpt-oss-120b model with the Groq inference provider
4	---
5	
6	# Calling an LLM via Groq
7	
8	These instructions allow you write code to call an LLM with Groq specified as the inference provider.  
9	This method uses LiteLLM natively and includes error handling for Groq rate limits.
10	
11	## Setup
12	
13	The GROQ_API_KEY must be set in the .env file and loaded in as an environment variable.  
14	
15	The uv project must include litellm, pydantic, and tenacity.
16	`uv add litellm pydantic tenacity`
17	
18	## Rate Limit Handling (429 Errors)
19	
20	Groq enforces strict tokens-per-minute (TPM) and requests-per-minute (RPM) limits. 
21	The cleanest way to handle these errors is combining LiteLLM's internal error types with the `tenacity` library for exponential backoff retries.
22	
23	```python
24	import litellm
25	from litellm import completion
26	from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
27	
28	# Retry only on specific Groq rate limits or connection overloads
29	@retry(
30	    reraise=True,
31	    stop=stop_after_attempt(5),
32	    wait=wait_exponential(multiplier=2, min=4, max=64),
33	    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError))
34	)
35	def completion_with_backoff(**kwargs):
36	    # litellm does not yet recognize that Groq's gpt-oss models accept
37	    # `reasoning_effort`, so it must be allowlisted explicitly or the call
38	    # is rejected with UnsupportedParamsError before reaching Groq.
39	    kwargs.setdefault("allowed_openai_params", ["reasoning_effort"])
40	    return completion(**kwargs)
41	```
42	
43	## Code snippets
44	
45	Use code like these examples in order to use Groq securely.
46	
47	### Imports and constants
48	
49	```python
50	import litellm
51	from litellm import completion
52	from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
53	
54	# Note: the model lives under the `openai/` namespace on Groq, not bare `gpt-oss-120b`
55	MODEL = "groq/openai/gpt-oss-120b"
56	
57	@retry(
58	    reraise=True,
59	    stop=stop_after_attempt(5),
60	    wait=wait_exponential(multiplier=2, min=4, max=64),
61	    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError))
62	)
63	def completion_with_backoff(**kwargs):
64	    kwargs.setdefault("allowed_openai_params", ["reasoning_effort"])
65	    return completion(**kwargs)
66	```
67	
68	### Code to call via Groq for a text response
69	
70	```python
71	response = completion_with_backoff(model=MODEL, messages=messages, reasoning_effort="high")
72	result = response.choices[0].message.content
73	```
74	
75	### Code to call via Groq for a Structured Outputs response
76	
77	```python
78	response = completion_with_backoff(model=MODEL, messages=messages, response_format=MyBaseModelSubclass, reasoning_effort="high")
79	result = response.choices[0].message.content
80	result_as_object = MyBaseModelSubclass.model_validate_json(result)
81	```