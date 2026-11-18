"""Local chat, typed extraction, and a small tool-using Pydantic AI agent."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Literal
from urllib.parse import urlparse

# Keep CLI output focused on the answer (especially when returning JSON).
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic import BaseModel, Field
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.usage import UsageLimits


class ProjectBrief(BaseModel):
    """A compact project brief extracted from the user's text."""

    objective: str
    tasks: list[str] = Field(min_length=1, max_length=8)
    open_questions: list[str]


def estimate_download_minutes(size_gb: float, speed_mbps: float) -> float:
    """Estimate ideal download minutes from decimal gigabytes and megabits/second.

    Args:
        size_gb: Download size in decimal GB, zero or larger.
        speed_mbps: Connection speed in megabits per second, greater than zero.
    """
    if size_gb < 0 or speed_mbps <= 0:
        raise ValueError("Size must be nonnegative and speed must be positive.")
    return round(size_gb * 8_000 / speed_mbps / 60, 2)


def make_agent(mode: Literal["chat", "extract", "tools"], model: OllamaModel) -> Agent:
    if mode == "extract":
        # Pydantic AI's default typed output uses tool calling, which Gemma 3
        # does not support in Ollama. NativeOutput uses JSON schema instead.
        return Agent(
            model,
            output_type=NativeOutput(ProjectBrief),
            instructions="Extract a brief. Record missing information as open questions.",
            retries=2,
        )
    if mode == "tools":
        return Agent(
            model,
            tools=[estimate_download_minutes],
            instructions=(
                "Use estimate_download_minutes for download-time arithmetic. "
                "Report its result and explain that real downloads can take longer. "
                "Do not invent a tool result."
            ),
            retries=2,
        )
    return Agent(model, instructions="Be clear and concise.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["chat", "extract", "tools"])
    parser.add_argument("prompt", help="Prompt or source text, in quotes")
    parser.add_argument("--model", help="Ollama model tag (overrides the environment)")
    args = parser.parse_args()
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    parsed = urlparse(base_url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Use a loopback Ollama URL; use SSH forwarding for a remote Spark.")
    if parsed.scheme not in {"http", "https"} or parsed.path.rstrip("/") != "/v1":
        parser.error("OLLAMA_BASE_URL must be an http(s) URL ending in /v1.")
    tag = args.model or os.getenv(
        "OLLAMA_TOOL_MODEL" if args.mode == "tools" else "OLLAMA_MODEL",
        "gemma4:26b" if args.mode == "tools" else "gemma4:e4b",
    )
    if tag.endswith("-cloud") or ":cloud" in tag:
        parser.error("Choose a locally downloaded model, not an Ollama Cloud model.")
    try:
        model = OllamaModel(tag, provider=OllamaProvider(base_url=base_url))
        agent = make_agent(args.mode, model)
        result = agent.run_sync(
            args.prompt,
            model_settings={"temperature": 0, "max_tokens": 2048, "timeout": 300},
            usage_limits=UsageLimits(request_limit=6),
        )
        if args.mode == "tools":
            # Show whether the model actually used the Python tool.
            calls = [
                part for message in result.all_messages()
                for part in message.parts if part.part_kind == "tool-call"
            ]
            if not any(part.tool_name == "estimate_download_minutes" for part in calls):
                print("The model did not call the tool; try the README's example prompt.", file=sys.stderr)
                return 1
            for part in calls:
                print(f"Tool call: {part.tool_name}({part.args})", file=sys.stderr)
        output = result.output
        print(output.model_dump_json(indent=2) if isinstance(output, BaseModel) else output)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "Check bash scripts/doctor.sh and ollama list. "
            "The tools demo needs a tool-capable model such as gemma4:26b.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
