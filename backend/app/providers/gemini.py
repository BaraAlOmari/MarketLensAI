"""Thin wrapper over google-genai for JSON-schema output, via one of two APIs.

- "interactions" (default; the Stage 1 generator): `client.aio.interactions.create(...)`.
- "generate_content" (query extraction): `client.aio.models.generate_content(...)` with
  `response_json_schema`. On 2026-10-14 the same model, prompt and 27-field schema gave
  mislabelled fields through Interactions ("2 bedroom" -> storage_gb = 2, "2020 or newer" ->
  a price under 2020) and correct ones through generateContent (bedrooms = 2, min_year = 2020).

Verified 2026-10-10 against ai.google.dev/gemini-api/docs/structured-output and the
installed SDK (google-genai 2.29.0): `client.aio.interactions.create(...)` with
`response_format={"type": "text", "mime_type": "application/json", "schema": ...}`
returns an Interaction whose `output_text` holds the JSON and `usage` the token counts.

Retries: the Interactions client retries on its own by default (3 retries, connection
errors included), which nested inside `with_retries` let one bad batch hang for over an
hour on 2026-10-12. The client is created with the minimum the SDK allows (1 internal
retry), and each attempt gets a hard `asyncio.wait_for` deadline so `with_retries` stays
in control of total time.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Literal

from google import genai
from google.genai import types

from app.providers.retry import with_retries


@dataclass(frozen=True)
class JsonResult:
    text: str
    input_tokens: int
    output_tokens: int
    thought_tokens: int


class GeminiJsonClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 240.0,
        max_attempts: int = 6,
        base_delay_s: float = 5.0,
        api: Literal["interactions", "generate_content"] = "interactions",
    ) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )
        self.model = model
        self._timeout_s = timeout_s
        self._max_attempts = max_attempts
        self._base_delay_s = base_delay_s
        self.api = api

    async def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        thinking_level: str = "low",
    ) -> JsonResult:
        call = self._interactions if self.api == "interactions" else self._generate_content

        async def attempt():
            return await asyncio.wait_for(
                call(system, prompt, schema, thinking_level), timeout=self._timeout_s + 10
            )

        return await with_retries(
            attempt, max_attempts=self._max_attempts, base_delay_s=self._base_delay_s
        )

    async def _interactions(self, system, prompt, schema, thinking_level) -> JsonResult:
        interaction = await self._client.aio.interactions.create(
            model=self.model,
            system_instruction=system,
            input=prompt,
            response_format={"type": "text", "mime_type": "application/json", "schema": schema},
            generation_config={"thinking_level": thinking_level},
            store=False,
            timeout=self._timeout_s,
        )
        usage = interaction.usage
        return JsonResult(
            text=interaction.output_text or "",
            input_tokens=(usage.total_input_tokens or 0) if usage else 0,
            output_tokens=(usage.total_output_tokens or 0) if usage else 0,
            thought_tokens=(usage.total_thought_tokens or 0) if usage else 0,
        )

    async def _generate_content(self, system, prompt, schema, thinking_level) -> JsonResult:
        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_json_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                http_options=types.HttpOptions(timeout=int(self._timeout_s * 1000)),
            ),
        )
        usage = response.usage_metadata
        return JsonResult(
            text=response.text or "",
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            thought_tokens=(usage.thoughts_token_count or 0) if usage else 0,
        )
