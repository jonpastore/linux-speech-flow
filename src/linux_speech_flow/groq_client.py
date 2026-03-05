import requests

GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"


def validate_api_key(api_key: str) -> dict:
    if not api_key.startswith("gsk_") or len(api_key) < 20:
        return {"ok": False, "message": "Invalid API key format"}

    try:
        response = requests.get(
            GROQ_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return {
            "ok": False,
            "message": "Could not connect to Groq — check your internet connection",
        }

    if response.status_code == 200:
        return {"ok": True}
    if response.status_code == 401:
        return {"ok": False, "message": "Invalid API key"}
    return {"ok": False, "message": f"Unexpected response ({response.status_code})"}
