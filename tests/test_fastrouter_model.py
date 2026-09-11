"""
tests/test_fastrouter_model.py — Unit tests for FastRouter LLM model instantiation.
"""

from unittest.mock import MagicMock, patch
from config.settings import Settings
from agents.base_agent import BaseAgent


class DummyAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "You are a test agent."

    def get_tools(self) -> list:
        return []


def test_fastrouter_model_initialization():
    settings = Settings(
        llm_provider="fastrouter",
        fastrouter_api_key="test_fastrouter_key",
        fastrouter_base_url="https://api.fastrouter.ai/api/v1",
        fastrouter_model_id="anthropic/claude-3.5-sonnet",
    )

    agent = DummyAgent(settings)

    with patch("strands.models.openai.OpenAIModel") as mock_openai_model:
        model = agent._get_model()

        mock_openai_model.assert_called_once_with(
            client_args={
                "api_key": "test_fastrouter_key",
                "base_url": "https://api.fastrouter.ai/api/v1",
            },
            model_id="anthropic/claude-3.5-sonnet",
            params={
                "temperature": 0.3,
            },
        )
        assert model == mock_openai_model.return_value
