"""Exercise the actual Ollama HTTP adapter without a model or network."""

import json
import unittest

import httpx2
from openai import AsyncOpenAI
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.usage import UsageLimits

from examples.local_agent import ProjectBrief, make_agent


class OllamaExamplesTest(unittest.IsolatedAsyncioTestCase):
    async def run_example(self, mode, responses, tag=None):
        requests = []

        def respond(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            requests.append(json.loads(request.content))
            self.assertLessEqual(len(requests), len(responses), "Unexpected extra model call")
            message, finish = responses[len(requests) - 1]
            return httpx2.Response(200, json={
                "id": f"test-{len(requests)}", "object": "chat.completion", "created": 0,
                "model": requests[-1]["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })

        async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
            client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="unused", http_client=http)
            model = OllamaModel(
                tag or ("gemma4:26b" if mode == "tools" else "gemma4:e4b"),
                provider=OllamaProvider(openai_client=client),
            )
            agent = make_agent(mode, model)
            result = await agent.run("Test prompt", usage_limits=UsageLimits(request_limit=6))
        return result, requests

    async def test_chat_does_not_send_tools(self):
        result, requests = await self.run_example("chat", [
            ({"role": "assistant", "content": "Hello locally."}, "stop"),
        ])
        self.assertEqual(result.output, "Hello locally.")
        self.assertNotIn("tools", requests[0])

    async def test_gemma4_extraction_uses_native_schema_without_tools(self):
        brief = {"objective": "Summarise notes", "tasks": ["Collect examples"], "open_questions": []}
        result, requests = await self.run_example("extract", [
            ({"role": "assistant", "content": json.dumps(brief)}, "stop"),
        ])
        self.assertIsInstance(result.output, ProjectBrief)
        self.assertEqual(result.output.model_dump(), brief)
        self.assertEqual(requests[0]["response_format"]["type"], "json_schema")
        self.assertNotIn("tools", requests[0])

    async def test_gemma3_extraction_also_works_without_tools(self):
        brief = {"objective": "Summarise notes", "tasks": ["Collect examples"], "open_questions": []}
        result, requests = await self.run_example("extract", [
            ({"role": "assistant", "content": json.dumps(brief)}, "stop"),
        ], tag="gemma3:4b")
        self.assertEqual(result.output.model_dump(), brief)
        self.assertEqual(requests[0]["response_format"]["type"], "json_schema")
        self.assertNotIn("tools", requests[0])

    async def test_invalid_extraction_is_retried_and_validated(self):
        brief = {"objective": "Summarise notes", "tasks": [], "open_questions": []}
        fixed = {**brief, "tasks": ["Collect examples"]}
        result, requests = await self.run_example("extract", [
            ({"role": "assistant", "content": json.dumps(brief)}, "stop"),
            ({"role": "assistant", "content": json.dumps(fixed)}, "stop"),
        ])
        self.assertEqual(len(requests), 2)
        self.assertEqual(result.output.tasks, ["Collect examples"])

    async def test_tool_is_executed_and_its_result_returned_to_model(self):
        result, requests = await self.run_example("tools", [
            ({"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function", "function": {
                    "name": "estimate_download_minutes",
                    "arguments": '{"size_gb":17,"speed_mbps":100}',
                },
            }]}, "tool_calls"),
            ({"role": "assistant", "content": "About 22.67 minutes."}, "stop"),
        ])
        self.assertEqual(len(requests), 2)
        tool_results = [m for m in requests[1]["messages"] if m["role"] == "tool"]
        self.assertEqual(float(tool_results[0]["content"]), 22.67)
        self.assertEqual(result.output, "About 22.67 minutes.")


if __name__ == "__main__":
    unittest.main()
