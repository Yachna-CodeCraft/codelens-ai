from anthropic import AsyncAnthropic

from app.config import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None

ASSISTANT_SYSTEM = (
    "You are CodeLens, an assistant that explains a software repository to developers. "
    "Answer only from the code excerpts provided. Reference files as `path:start-end`. "
    "If the excerpts do not contain the answer, say so instead of guessing."
)


def ai_enabled() -> bool:
    return _client is not None


async def complete(system: str, prompt: str, max_tokens: int = 1000) -> str:
    response = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def format_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"### {c['file_path']}:{c['start_line']}-{c['end_line']}\n{c['content']}" for c in chunks
    )


async def answer_question(question: str, chunks: list[dict]) -> str:
    if not ai_enabled():
        return (
            "AI is not configured (set ANTHROPIC_API_KEY). "
            "Here are the most relevant code excerpts for your question."
        )
    prompt = f"Code excerpts:\n\n{format_context(chunks)}\n\nQuestion: {question}"
    return await complete(ASSISTANT_SYSTEM, prompt, max_tokens=1200)
