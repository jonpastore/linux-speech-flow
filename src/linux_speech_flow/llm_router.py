"""Central provider routing: cloud (Groq/x.ai/Gemini) vs local LiteLLM endpoint.

Call sites use these helpers instead of branching on provider_mode themselves,
so the cloud-vs-litellm decision lives in exactly one place. In litellm mode a
single OpenAI-compatible client (LiteLLM) serves both transcription and chat.
"""

import groq
import openai


def is_litellm(config: dict) -> bool:
    return config.get("provider_mode", "cloud") == "litellm"


def litellm_client(config: dict) -> openai.OpenAI:
    return openai.OpenAI(
        base_url=config.get("litellm_base_url", ""),
        api_key=config.get("litellm_api_key", ""),
        max_retries=0,
        timeout=120.0,
    )


def transcription_client_model(config: dict):
    """Return (client, model_name) for the Whisper transcription call."""
    if is_litellm(config):
        return litellm_client(config), config.get(
            "litellm_whisper_model", "whisper-turbo"
        )
    client = groq.Groq(
        api_key=config.get("groq_api_key", ""), max_retries=0, timeout=120.0
    )
    return client, config.get("whisper_model", "whisper-large-v3-turbo")


def chat_client_model(config: dict, cloud_model: str):
    """Return (client, model_name) for a chat/completion call.

    cloud_model is the Groq model to use in cloud mode; ignored in litellm mode.
    """
    if is_litellm(config):
        return litellm_client(config), config.get("litellm_chat_model", "gemini")
    client = groq.Groq(
        api_key=config.get("groq_api_key", ""), max_retries=0, timeout=120.0
    )
    return client, cloud_model


def synthesis_alias(config: dict, role: str) -> str:
    """Map a synthesis role ('groq'|'grok'|'gemini') to a LiteLLM model name.

    In cloud mode the role is returned unchanged (callers handle it natively).
    In litellm mode 'groq' maps to the configured chat model; the frontier
    roles keep their own LiteLLM aliases.
    """
    if is_litellm(config) and role == "groq":
        return config.get("litellm_chat_model", "gemini")
    return role


def retryable_errors(config: dict) -> tuple:
    if is_litellm(config):
        return (openai.APIConnectionError, openai.RateLimitError)
    return (groq.APIConnectionError, groq.RateLimitError)


def demo() -> None:
    cloud = {
        "provider_mode": "cloud",
        "groq_api_key": "k",
        "whisper_model": "whisper-large-v3-turbo",
    }
    lite = {
        "provider_mode": "litellm",
        "litellm_base_url": "http://cerberus-ai:4000/v1",
        "litellm_api_key": "sk-x",
        "litellm_whisper_model": "whisper-turbo",
        "litellm_chat_model": "gemini",
    }

    assert is_litellm(lite) and not is_litellm(cloud)

    c_client, c_model = transcription_client_model(cloud)
    assert isinstance(c_client, groq.Groq)
    assert c_model == "whisper-large-v3-turbo"

    l_client, l_model = transcription_client_model(lite)
    assert isinstance(l_client, openai.OpenAI)
    assert l_model == "whisper-turbo"

    assert chat_client_model(cloud, "llama-x")[1] == "llama-x"
    assert isinstance(chat_client_model(cloud, "llama-x")[0], groq.Groq)
    assert chat_client_model(lite, "llama-x")[1] == "gemini"
    assert isinstance(chat_client_model(lite, "llama-x")[0], openai.OpenAI)

    assert synthesis_alias(cloud, "groq") == "groq"
    assert synthesis_alias(cloud, "grok") == "grok"
    assert synthesis_alias(lite, "groq") == "gemini"
    assert synthesis_alias(lite, "grok") == "grok"
    assert synthesis_alias(lite, "gemini") == "gemini"

    assert retryable_errors(cloud) == (groq.APIConnectionError, groq.RateLimitError)
    assert retryable_errors(lite) == (
        openai.APIConnectionError,
        openai.RateLimitError,
    )

    print("llm_router self-check OK")


if __name__ == "__main__":
    demo()
