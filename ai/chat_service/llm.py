from collections.abc import AsyncGenerator
import ollama
from ai.config import settings


def generate_response(prompt: str, system_prompt: str | None = None) -> str:
    """Generate a response using llama3:8b via Ollama."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = ollama.chat(
        model=settings.LLM_MODEL,
        messages=messages,
    )
    return response["message"]["content"]


async def generate_response_stream(
    prompt: str, system_prompt: str | None = None
) -> AsyncGenerator[str, None]:
    """Stream a response from llama3:8b via Ollama."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    stream = ollama.chat(
        model=settings.LLM_MODEL,
        messages=messages,
        stream=True,
    )
    for chunk in stream:
        content = chunk["message"]["content"]
        if content:
            yield content
