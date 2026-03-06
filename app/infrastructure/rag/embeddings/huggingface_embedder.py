"""HuggingFace embeddings implementation with caching and retry logic."""

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

from app.domain.rag.interfaces import IEmbedder
from app.domain.rag.value_objects import EmbeddingVector
from app.domain.rag.exceptions import EmbeddingError
from app.config.settings import settings

logger = logging.getLogger(__name__)


class HuggingFaceEmbedder(IEmbedder):
    """Embedder using HuggingFace sentence transformers with caching."""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: str = 'cpu',
        cache_embeddings: bool = True
    ):
        """
        Initialize HuggingFace embedder.
        
        Args:
            model_name: HuggingFace model (default from settings)
            device: 'cpu' or 'cuda'
            cache_embeddings: Whether to cache computed embeddings
        """
        self._model_name = model_name or settings.HUGGINGFACE_EMBEDDING_MODEL
        self._device = device
        self._cache_enabled = cache_embeddings
        self._embedding_cache = {}
        
        try:
            logger.info(f"Initializing HuggingFace embedder: {self._model_name}")
            
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self._model_name,
                model_kwargs={'device': device},
                encode_kwargs={'normalize_embeddings': True}
            )
            
            # Get dimension by embedding a test string
            test_vec = self._embeddings.embed_query("test")
            self._dimension = len(test_vec)
            
            logger.info(
                f"Initialized embedder: {self._model_name} "
                f"(dimension={self._dimension}, device={device})"
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {e}", exc_info=True)
            raise EmbeddingError(
                f"Failed to initialize embedder: {str(e)}",
                details={"model": self._model_name, "error": str(e)}
            )
    
    @staticmethod
    def _get_cache_key(text: str) -> str:
        """Generate a cache key for text."""
        return hashlib.sha256(text.encode()).hexdigest()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Embedding generation failed, retrying... "
            f"Attempt {retry_state.attempt_number}"
        )
    )
    async def embed_text(self, text: str) -> EmbeddingVector:
        """Generate embedding for single text with caching."""
        try:
            # Check cache
            if self._cache_enabled:
                cache_key = self._get_cache_key(text)
                if cache_key in self._embedding_cache:
                    logger.debug("Embedding cache hit")
                    vector_values = self._embedding_cache[cache_key]
                    return EmbeddingVector(
                        values=vector_values,
                        model=self._model_name,
                        dimension=self._dimension
                    )
            
            # Generate embedding
            vector = self._embeddings.embed_query(text)
            
            # Cache result
            if self._cache_enabled:
                self._embedding_cache[cache_key] = vector
            
            return EmbeddingVector(
                values=vector,
                model=self._model_name,
                dimension=self._dimension
            )
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            raise EmbeddingError(
                f"Failed to generate embedding: {str(e)}",
                details={"text_length": len(text), "error": str(e)}
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Batch embedding failed, retrying... "
            f"Attempt {retry_state.attempt_number}"
        )
    )
    async def embed_batch(self, texts: List[str]) -> List[EmbeddingVector]:
        """Generate embeddings for multiple texts with batch optimization."""
        try:
            vectors = self._embeddings.embed_documents(texts)
            
            # Cache results
            if self._cache_enabled:
                for text, vector in zip(texts, vectors):
                    cache_key = self._get_cache_key(text)
                    self._embedding_cache[cache_key] = vector
            
            return [
                EmbeddingVector(
                    values=vec,
                    model=self._model_name,
                    dimension=self._dimension
                )
                for vec in vectors
            ]
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}", exc_info=True)
            raise EmbeddingError(
                f"Failed to generate batch embeddings: {str(e)}",
                details={"batch_size": len(texts), "error": str(e)}
            )
    
    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        return self._dimension
    
    @property
    def model_name(self) -> str:
        """Name of the embedding model."""
        return self._model_name
    
    def clear_cache(self) -> None:
        """Clear embedding cache (useful for memory management)."""
        self._embedding_cache.clear()
        logger.debug("Embedding cache cleared")
