import os
from typing import Type, TypeVar

import instructor
from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Points at the local Ollama server only. "ollama" is a placeholder api_key —
# Ollama's OpenAI-compatible endpoint doesn't check it, and no request ever
# leaves this machine.
_raw_client = OpenAI(
    base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    api_key="ollama",
)
_client = instructor.from_openai(_raw_client, mode=instructor.Mode.JSON)

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "qwen2.5:7b")


def generate(prompt: str, response_model: Type[T], model: str = DEFAULT_MODEL) -> T:
    """Call the local LLM and return output validated against response_model.

    Instructor retries automatically (with the validation error fed back to
    the model) if the first response doesn't fit the schema.
    """
    return _client.chat.completions.create(
        model=model,
        response_model=response_model,
        messages=[{"role": "user", "content": prompt}],
        max_retries=2,
    )
