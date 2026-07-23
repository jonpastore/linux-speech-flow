import concurrent.futures
import json
import logging
import math
from datetime import datetime

from groq import Groq

from linux_speech_flow.config import load_config

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """Analyze the conversation transcript provided. The following qualifying context was provided by the user:
{qualifying_answers}

Return a JSON object with this exact schema:
{{
  "title": "brief descriptive title (3-8 words, suitable for a filename)",
  "summary": "2-4 paragraph executive summary calibrated to the stated audience and complexity",
  "confidence": 0.85,
  "questions": ["question to clarify ambiguity X", "question to clarify Y"],
  "action_items": ["action item 1 with owner if known", "action item 2"]
}}
confidence is a float 0.0-1.0 indicating how complete your understanding is given the transcript and qualifying context.
If confidence >= 0.95, set questions to an empty list.
"""


def conv_filename(title: str = "untitled") -> str:
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
    safe = safe.strip().replace(" ", "-")[:50]
    return f"{ts}_{safe}.txt"


def coalesce_file(
    save_path: str,
    metadata: dict,
    summary: str,
    qa_rounds: list,
    transcript: str,
    confidence: float = 0.0,
    action_items: list | None = None,
    prompt: str = "",
) -> None:
    lines = []
    lines.append(f"Date: {metadata.get('date', '')}")
    lines.append(f"Duration: {metadata.get('duration', '')}")
    lines.append(f"Chunks: {metadata.get('chunk_count', '')}")
    lines.append(f"Models: {metadata.get('models_used', 'None')}")
    if confidence > 0:
        lines.append(f"Confidence: {int(confidence * 100)}%")
    lines.append("")
    lines.append("## Summary")
    lines.append(summary or "(none)")

    if action_items:
        lines.append("")
        lines.append("## Action Items")
        for item in action_items:
            lines.append(f"- {item}")

    if qa_rounds:
        lines.append("")
        lines.append("## Q&A")
        for round_ in qa_rounds:
            lines.append(f"**AI:** {round_['question']}")
            lines.append(f"**You:** {round_['answer']}")
            lines.append("")

    lines.append("")
    lines.append("## Transcript")
    lines.append(transcript)

    if prompt:
        lines.append("")
        lines.append("## Analysis Prompt")
        lines.append(prompt)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class ConversationPipeline:
    def __init__(self):
        config = load_config()
        self._groq = Groq(
            api_key=config.get("groq_api_key", ""),
            max_retries=0,
        )

    def transcribe_chunk(self, wav_path: str) -> str:
        """Send one WAV chunk to Groq Whisper; return raw transcript text.
        Raises on API error (caller handles retry/logging).
        """
        text, _ = self.transcribe_chunk_verbose(wav_path)
        return text

    def transcribe_chunk_verbose(self, wav_path: str) -> tuple[str, float]:
        """Like transcribe_chunk but also returns confidence (0.0–1.0).
        Confidence is derived from avg_logprob across segments; 0.0 if no segments.
        """
        config = load_config()
        with open(wav_path, "rb") as f:
            response = self._groq.audio.transcriptions.create(
                file=("chunk.wav", f),
                model=config.get("whisper_model", "whisper-large-v3-turbo"),
                response_format="verbose_json",
            )
        text = (response.text or "").strip()
        segments = getattr(response, "segments", None) or []
        if segments:
            avg_lp = sum(getattr(s, "avg_logprob", -1.0) for s in segments) / len(
                segments
            )
            confidence = max(0.0, min(1.0, math.exp(avg_lp)))
        else:
            confidence = 0.0
        return text, confidence

    def analyze(
        self, transcript: str, prompt: str, qualifying_answers: str, models: list[str]
    ) -> dict:
        """Fire all selected models in parallel; return synthesized result.

        Args:
            transcript: Full coalesced transcript text.
            prompt: User's per-session prompt (editable in post-stop dialog).
            qualifying_answers: Newline-joined user answers to qualifying questions.
            models: List of model names to call; each must be one of
                    'groq', 'grok', 'gemini'.

        Returns dict with keys: title, summary, confidence, questions, action_items.
        """
        config = load_config()
        system = ANALYSIS_SYSTEM_PROMPT.format(
            qualifying_answers=qualifying_answers or "(none provided)"
        )
        full_content = f"{prompt}\n\n## Transcript\n{transcript}"

        model_results = {}
        with concurrent.futures.ThreadPoolExecutor() as pool:
            futures = {}
            if "groq" in models:
                futures[pool.submit(self._call_groq, system, full_content, config)] = (
                    "groq"
                )
            if "grok" in models:
                futures[pool.submit(self._call_grok, system, full_content, config)] = (
                    "grok"
                )
            if "gemini" in models:
                futures[
                    pool.submit(self._call_gemini, system, full_content, config)
                ] = "gemini"
            for future, name in futures.items():
                try:
                    model_results[name] = future.result(timeout=90)
                except Exception as exc:
                    logger.error("Model %s failed: %s", name, exc)
                    model_results[name] = {"error": str(exc)}

        if len(model_results) == 1:
            return next(iter(model_results.values()))

        meta_model = config.get("conv_meta_model", "groq")
        return self.synthesize(model_results, meta_model, config)

    def synthesize(
        self, model_results: dict, meta_model: str, config: dict | None = None
    ) -> dict:
        """Call meta_model to merge all model responses into one unified result.

        model_results: {model_name: parsed_dict_or_error_dict}
        Returns the same schema as ANALYSIS_SYSTEM_PROMPT.
        """
        if config is None:
            config = load_config()
        combined = json.dumps(model_results, indent=2)
        synthesis_prompt = (
            "You have received the following analysis results from multiple AI models for the same conversation transcript.\n"
            "Synthesize them into a single unified result. Resolve any contradictions by using the most complete and accurate information.\n"
            "Return a JSON object with the same schema: title, summary, confidence, questions, action_items.\n\n"
            f"Model responses:\n{combined}"
        )
        system = ANALYSIS_SYSTEM_PROMPT.format(
            qualifying_answers="(synthesis pass — see model responses below)"
        )
        try:
            if meta_model == "groq":
                return self._call_groq(system, synthesis_prompt, config)
            elif meta_model == "grok":
                return self._call_grok(system, synthesis_prompt, config)
            elif meta_model == "gemini":
                return self._call_gemini(system, synthesis_prompt, config)
        except Exception as exc:
            logger.error("Synthesis call failed: %s", exc)
        for r in model_results.values():
            if "error" not in r:
                return r
        return {
            "title": "untitled",
            "summary": "",
            "confidence": 0.0,
            "questions": [],
            "action_items": [],
        }

    def continue_qa(
        self,
        current_result: dict,
        question: str,
        answer: str,
        transcript: str,
        models: list[str],
    ) -> dict:
        """Submit one Q&A round and get an updated analysis result.

        Feeds the question+answer back to the same models so they can refine
        their analysis. Returns updated dict with same schema.
        """
        qa_context = f"Previous AI question: {question}\nUser answer: {answer}\n"
        updated_prompt = (
            "You previously analyzed a conversation transcript. The user has provided "
            "additional context via Q&A. Update your analysis incorporating this new information.\n"
            f"{qa_context}"
        )
        return self.analyze(transcript, updated_prompt, qa_context, models)

    def _call_groq(self, system: str, content: str, config: dict) -> dict:
        response = self._groq.chat.completions.create(
            model=config.get(
                "conv_groq_model", "meta-llama/llama-4-scout-17b-16e-instruct"
            ),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=4096,
        )
        return self._parse_result(response.choices[0].message.content)

    def _call_grok(self, system: str, content: str, config: dict) -> dict:
        from openai import OpenAI

        client = OpenAI(
            api_key=config.get("grok_api_key", ""),
            base_url="https://api.x.ai/v1",
        )
        response = client.chat.completions.create(
            model=config.get("grok_model", "grok-3-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=4096,
        )
        return self._parse_result(response.choices[0].message.content)

    def _call_gemini(self, system: str, content: str, config: dict) -> dict:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.get("gemini_api_key", ""))
        response = client.models.generate_content(
            model=config.get("gemini_model", "gemini-2.5-flash"),
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )
        return self._parse_result(response.text)

    def _parse_result(self, raw: str) -> dict:
        """Parse JSON response; return schema-conformant dict with safe defaults."""
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Model returned non-JSON: %r", (raw or "")[:200])
            return {
                "title": "untitled",
                "summary": raw,
                "confidence": 0.0,
                "questions": [],
                "action_items": [],
            }
        return {
            "title": str(parsed.get("title", "untitled")),
            "summary": str(parsed.get("summary", "")),
            "confidence": float(parsed.get("confidence", 0.0)),
            "questions": list(parsed.get("questions", [])),
            "action_items": list(parsed.get("action_items", [])),
        }
