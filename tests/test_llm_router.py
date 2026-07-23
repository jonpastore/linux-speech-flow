"""Tests for the cloud-vs-litellm provider router. No network."""

import groq
import openai

from linux_speech_flow import llm_router

_CLOUD = {
    "provider_mode": "cloud",
    "groq_api_key": "gsk_test",
    "whisper_model": "whisper-large-v3-turbo",
}

_LITE = {
    "provider_mode": "litellm",
    "litellm_base_url": "http://cerberus-ai:4000/v1",
    "litellm_api_key": "sk-test",
    "litellm_whisper_model": "whisper-turbo",
    "litellm_chat_model": "gemini",
}


class TestIsLitellm:
    def test_cloud(self):
        assert llm_router.is_litellm(_CLOUD) is False

    def test_litellm(self):
        assert llm_router.is_litellm(_LITE) is True

    def test_default_is_cloud(self):
        assert llm_router.is_litellm({}) is False


class TestTranscriptionClientModel:
    def test_cloud(self):
        client, model = llm_router.transcription_client_model(_CLOUD)
        assert isinstance(client, groq.Groq)
        assert model == "whisper-large-v3-turbo"

    def test_litellm(self):
        client, model = llm_router.transcription_client_model(_LITE)
        assert isinstance(client, openai.OpenAI)
        assert model == "whisper-turbo"

    def test_litellm_client_uses_configured_base_url(self):
        client, _ = llm_router.transcription_client_model(_LITE)
        assert str(client.base_url).rstrip("/") == "http://cerberus-ai:4000/v1"


class TestChatClientModel:
    def test_cloud_uses_passed_model(self):
        client, model = llm_router.chat_client_model(_CLOUD, "llama-x")
        assert isinstance(client, groq.Groq)
        assert model == "llama-x"

    def test_litellm_uses_configured_chat_model(self):
        client, model = llm_router.chat_client_model(_LITE, "llama-x")
        assert isinstance(client, openai.OpenAI)
        assert model == "gemini"


class TestSynthesisAlias:
    def test_cloud_passthrough(self):
        assert llm_router.synthesis_alias(_CLOUD, "groq") == "groq"
        assert llm_router.synthesis_alias(_CLOUD, "grok") == "grok"
        assert llm_router.synthesis_alias(_CLOUD, "gemini") == "gemini"

    def test_litellm_maps_groq_to_chat_model(self):
        assert llm_router.synthesis_alias(_LITE, "groq") == "gemini"

    def test_litellm_keeps_frontier_roles(self):
        assert llm_router.synthesis_alias(_LITE, "grok") == "grok"
        assert llm_router.synthesis_alias(_LITE, "gemini") == "gemini"


class TestRetryableErrors:
    def test_cloud(self):
        assert llm_router.retryable_errors(_CLOUD) == (
            groq.APIConnectionError,
            groq.RateLimitError,
        )

    def test_litellm(self):
        assert llm_router.retryable_errors(_LITE) == (
            openai.APIConnectionError,
            openai.RateLimitError,
        )


def test_demo_self_check_passes():
    llm_router.demo()
