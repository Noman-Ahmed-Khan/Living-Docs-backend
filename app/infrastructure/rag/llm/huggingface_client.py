"""Language Model client using HuggingFace Inference API."""

import logging
from typing import Optional, Literal

from huggingface_hub import InferenceClient
from huggingface_hub.errors import BadRequestError, HfHubHTTPError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.domain.rag.interfaces import ILLMClient
from app.domain.rag.exceptions import LLMError
from app.config.settings import settings

logger = logging.getLogger(__name__)

CallMode = Literal["chat", "text"]

# What's worth retrying 
# BadRequestError (400) = wrong model/provider config → never retry
# HfHubHTTPError 5xx    = server blip                 → retry
# ConnectionError etc.  = network blip                → retry

class _TransientError(Exception):
    """Wraps retryable failures so tenacity can target them precisely."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    if isinstance(exc, HfHubHTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        return status >= 500
    return False


class HuggingFaceLLMClient(ILLMClient):
    """
    LLM client backed by HuggingFace Serverless Inference API.

    Confirmed working models (free tier, April 2026):
      - Qwen/Qwen2.5-7B-Instruct          ← primary
      - meta-llama/Llama-3.1-8B-Instruct  ← reliable fallback
      - HuggingFaceH4/zephyr-7b-beta      ← occasionally unstable/offline

    Both use the chat_completion() endpoint (task=conversational).
    Provider is auto-selected by HF — do NOT pin to "hf-inference".
    """

    # Models confirmed live on free HF inference, in preference order.
    # Used by the fallback probe if the configured model fails.
    _FALLBACK_MODELS = [
        "Qwen/Qwen2.5-7B-Instruct",
        "meta-llama/Llama-3.1-8B-Instruct",
        "HuggingFaceH4/zephyr-7b-beta",
    ]

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        provider: Optional[str] = None,
    ):
        self._model_name = model_name or settings.HUGGINGFACE_LLM_MODEL
        self._api_key    = api_key    or settings.HUGGINGFACE_API_KEY
        self._default_temperature = temperature
        self._default_max_tokens  = max_tokens

        # Explicit provider override from settings (should be None/empty for Qwen)
        raw_provider = (
            provider
            if provider is not None
            else getattr(settings, "HUGGINGFACE_LLM_PROVIDER", None)
        )
        # Treat empty string same as None
        self._provider: Optional[str] = raw_provider or None

        try:
            logger.info(
                f"Initializing HuggingFace LLM client: {self._model_name} "
                f"(provider={self._provider or 'auto'})"
            )

            self._client = InferenceClient(
                model=self._model_name,
                token=self._api_key,
                provider=self._provider,
            )

            # Determine call mode once at startup — no per-request overhead
            self._call_mode: CallMode = self._resolve_call_mode()

            logger.info(
                f"LLM client ready | model={self._model_name} "
                f"call_mode={self._call_mode} "
                f"provider={self._provider or 'auto'}"
            )

        except LLMError:
            raise
        except Exception as exc:
            logger.error(f"Failed to initialize LLM client: {exc}", exc_info=True)
            raise LLMError(
                f"Failed to initialize LLM: {exc}",
                details={"model": self._model_name, "error": str(exc)},
            )

    # Public interface

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_TransientError),
        before_sleep=lambda rs: logger.warning(
            f"Transient LLM error — retrying (attempt {rs.attempt_number})"
        ),
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        stream: bool = False,
    ) -> str:
        """
        Generate a completion for *prompt*.

        Raises:
            ValueError:  empty prompt (caller bug, not retried)
            LLMError:    all other failures (config or generation)
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        try:
            if self._call_mode == "chat":
                result = self._call_chat(prompt, temperature, max_tokens)
            else:
                result = self._call_text(prompt, temperature, max_tokens)

            logger.info(
                f"LLM response | model={self._model_name} "
                f"mode={self._call_mode} "
                f"approx_words={len(result.split())}"
            )
            return result

        except ValueError:
            raise  # never retry empty-prompt bugs

        except BadRequestError as exc:
            # 400 = wrong model / provider config — retrying won't help
            logger.error(f"BadRequest from HF API: {exc}")
            raise LLMError(
                f"HF API rejected the request (400): {exc}",
                details={
                    "model":    self._model_name,
                    "provider": self._provider,
                    "mode":     self._call_mode,
                    "error":    str(exc),
                    "hint": (
                        "Confirmed working model: Qwen/Qwen2.5-7B-Instruct. "
                        "Set HUGGINGFACE_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct "
                        "and leave HUGGINGFACE_LLM_PROVIDER unset in .env"
                    ),
                },
            )

        except Exception as exc:
            if _is_transient(exc):
                logger.warning(f"Transient error, will retry: {exc}")
                raise _TransientError(str(exc)) from exc

            logger.error(f"LLM generation failed: {exc}", exc_info=True)
            raise LLMError(
                f"Failed to generate text: {exc}",
                details={
                    "model":         self._model_name,
                    "prompt_length": len(prompt),
                    "error":         str(exc),
                },
            )

    @property
    def model_name(self) -> str:
        return self._model_name

    # Call mode resolution

    def _resolve_call_mode(self) -> CallMode:
        """
        Determine whether to use chat_completion or text_generation.

        Resolution order:
          1. Live probe       (sends 1 token request, definitive)
          2. HF Hub metadata  (fastest, no inference cost fallback)
          3. Name heuristic   (last resort, no network needed)
        """
        mode = self._mode_from_live_probe()
        if mode:
            logger.debug(f"Call mode resolved from live probe: {mode}")
            return mode

        mode = self._mode_from_metadata()
        if mode:
            logger.debug(f"Call mode resolved from metadata: {mode}")
            return mode

        mode = "chat" if self._looks_like_chat_model() else "text"
        logger.debug(f"Call mode resolved from name heuristic: {mode}")
        return mode

    def _mode_from_metadata(self) -> Optional[CallMode]:
        """
        Parse HF Hub inferenceProviderMapping.

        The API returns either a list or dict depending on huggingface_hub
        version — we handle both.
        """
        try:
            from huggingface_hub import model_info as hf_model_info

            info = hf_model_info(
                self._model_name,
                expand="inferenceProviderMapping",
                token=self._api_key,
            )
            raw = getattr(info, "inference_provider_mapping", None)
            if not raw:
                return None

            # Normalise to iterable of entry objects
            entries = raw.values() if isinstance(raw, dict) else raw

            for entry in entries:
                task   = (getattr(entry, "task",   None) or "").lower()
                status = (getattr(entry, "status", None) or "").lower()

                # Skip providers that are explicitly down
                if status == "error":
                    continue

                if "conversational" in task or "chat" in task:
                    return "chat"
                if "text-generation" in task or "text_generation" in task:
                    return "text"

            return None

        except Exception as exc:
            logger.warning(f"Metadata probe failed for {self._model_name}: {exc}")
            return None

    def _mode_from_live_probe(self) -> Optional[CallMode]:
        """
        Send a minimal request to determine which endpoint accepts this model.
        Tries chat first (most common for modern instruct models).
        """
        probe = "Reply with one word: hello"

        try:
            self._client.chat_completion(
                messages=[{"role": "user", "content": probe}],
                max_tokens=5,
                temperature=0.01,
            )
            logger.debug(f"Live probe: chat_completion succeeded for {self._model_name}")
            return "chat"
        except Exception as exc:
            logger.debug(f"Live probe: chat_completion failed: {exc}")

        try:
            self._client.text_generation(
                prompt=probe,
                max_new_tokens=5,
                temperature=0.01,
            )
            logger.debug(f"Live probe: text_generation succeeded for {self._model_name}")
            return "text"
        except Exception as exc:
            logger.debug(f"Live probe: text_generation failed: {exc}")

        logger.warning(
            f"Both live probes failed for {self._model_name}. "
            f"Will fall back to name heuristic."
        )
        return None

    def _looks_like_chat_model(self) -> bool:
        """Keyword heuristic when metadata and live probe both unavailable."""
        keywords = {
            "instruct", "chat", "-it", "zephyr", "qwen",
            "vicuna", "alpaca", "orca", "wizard", "hermes",
            "openchat", "starling", "mistral", "mixtral",
            "llama", "phi", "gemma",
        }
        return any(kw in self._model_name.lower() for kw in keywords)

    # Low-level callers 

    def _call_chat(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """POST to /v1/chat/completions."""
        response = self._client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=max(temperature, 0.01),  # 0.0 rejected by some providers
        )
        if hasattr(response, "choices") and response.choices:
            return (response.choices[0].message.content or "").strip()
        logger.warning(f"Unexpected chat_completion response shape: {type(response)}")
        return str(response)

    def _call_text(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """POST to /text-generation."""
        response = self._client.text_generation(
            prompt=prompt,
            max_new_tokens=max_tokens,
            temperature=max(temperature, 0.01),
            return_full_text=False,
        )
        return response.strip() if isinstance(response, str) else str(response)