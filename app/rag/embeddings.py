"""Embedding generation with Hugging Face."""

import logging
import hashlib
from typing import List, Optional
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from app.settings import settings
from .exceptions import EmbeddingError


logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating embeddings with retry logic and caching.
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        cache_enabled: bool = True
    ):
        self.model = model or settings.HUGGINGFACE_EMBEDDING_MODEL
        self.cache_enabled = cache_enabled
        self._embeddings_model = None
        self._cache = {}
    
    @property
    def embeddings_model(self) -> HuggingFaceEmbeddings:
        """Lazy initialization of embeddings model."""
        if self._embeddings_model is None:
            logger.info(f"Initializing Hugging Face embeddings with model: {self.model}")
            self._embeddings_model = HuggingFaceEmbeddings(
                model_name=self.model
            )
        return self._embeddings_model
    
    @staticmethod
    def _get_cache_key(text: str) -> str:
        """Generate a cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            f"Embedding generation failed, retrying... Attempt {retry_state.attempt_number}"
        )
    )
    def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a query with retry logic.
        
        Args:
            text: Query text to embed
            
        Returns:
            List of floats representing the embedding
        """
        try:
            # Check cache
            if self.cache_enabled:
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    logger.debug("Embedding cache hit")
                    return self._cache[cache_key]
            
            # Generate embedding
            embedding = self.embeddings_model.embed_query(text)
            
            # Cache result
            if self.cache_enabled:
                self._cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingError(
                "Failed to generate query embedding",
                details={"error": str(e)}
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.
        
        Args:
            texts: List of document texts
            
        Returns:
            List of embeddings
        """
        try:
            # Process in batches to avoid rate limits
            batch_size = 100
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                embeddings = self.embeddings_model.embed_documents(batch)
                all_embeddings.extend(embeddings)
                logger.debug(f"Embedded batch {i // batch_size + 1}")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise EmbeddingError(
                "Failed to generate document embeddings",
                details={"error": str(e), "count": len(texts)}
            )
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")


# Module-level singleton
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Get embeddings model for LangChain integration.
    
    This maintains backward compatibility with existing code.
    """
    return get_embedding_service().embeddings_model