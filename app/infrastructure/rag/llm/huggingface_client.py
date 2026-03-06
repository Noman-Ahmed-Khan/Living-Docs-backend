"""Language Model client using HuggingFace Inference API."""

import logging
from typing import Optional

from langchain_huggingface import HuggingFaceEndpoint
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from app.domain.rag.interfaces import ILLMClient
from app.domain.rag.exceptions import LLMError
from app.config.settings import settings

logger = logging.getLogger(__name__)


class HuggingFaceLLMClient(ILLMClient):
    """Language model client using HuggingFace Inference API."""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512
    ):
        """
        Initialize HuggingFace LLM client.
        
        Args:
            model_name: HuggingFace model (default from settings)
            api_key: HuggingFace API key (default from settings)
            temperature: Default temperature for generation
            max_tokens: Default max tokens to generate
        """
        self._model_name = model_name or settings.HUGGINGFACE_LLM_MODEL
        self._api_key = api_key or settings.HUGGINGFACE_API_KEY
        self._default_temperature = temperature
        self._default_max_tokens = max_tokens
        
        try:
            logger.info(f"Initializing HuggingFace LLM client: {self._model_name}")
            
            self._llm = HuggingFaceEndpoint(
                repo_id=self._model_name,
                huggingfacehub_api_token=self._api_key,
                temperature=temperature,
                max_new_tokens=max_tokens,
                task="text-generation"
            )
            
            logger.info(f"Initialized LLM client: {self._model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}", exc_info=True)
            raise LLMError(
                f"Failed to initialize LLM: {str(e)}",
                details={"model": self._model_name, "error": str(e)}
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM generation failed, retrying... "
            f"Attempt {retry_state.attempt_number}"
        )
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        stream: bool = False
    ) -> str:
        """Generate text completion."""
        try:
            if not prompt or len(prompt.strip()) == 0:
                raise ValueError("Prompt cannot be empty")
            
            # Use HuggingFaceEndpoint's invoke method
            response = self._llm.invoke(
                prompt,
                temperature=temperature,
                max_new_tokens=max_tokens
            )
            
            # Extract text from response
            if isinstance(response, str):
                generated_text = response
            else:
                # Handle other response formats
                generated_text = str(response)
            
            logger.info(
                f"Generated text with {self._model_name} "
                f"(tokens={len(generated_text.split())}, "
                f"temp={temperature})"
            )
            
            return generated_text
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise LLMError(
                f"Failed to generate text: {str(e)}",
                details={
                    "prompt_length": len(prompt),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "error": str(e)
                }
            )
    
    @property
    def model_name(self) -> str:
        """Name of the LLM model."""
        return self._model_name
