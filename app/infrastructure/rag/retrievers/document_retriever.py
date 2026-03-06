"""Document retriever with multiple strategies."""

import logging
from typing import List, Optional
from uuid import UUID
from abc import ABC, abstractmethod

from app.domain.rag.interfaces import IRetriever, IEmbedder, IVectorStore
from app.domain.rag.entities import RetrievedChunk
from app.domain.rag.strategies import RetrievalStrategy
from app.domain.rag.exceptions import RetrievalError, NoContextFoundError
from app.domain.rag.value_objects import RetrieverConfig

logger = logging.getLogger(__name__)


class BaseRetriever(ABC, IRetriever):
    """Abstract base retriever."""
    
    def __init__(
        self,
        embedder: IEmbedder,
        vector_store: IVectorStore,
        config: RetrieverConfig
    ):
        """
        Initialize retriever.
        
        Args:
            embedder: Text embedding service
            vector_store: Vector database
            config: Retrieval configuration
        """
        self._embedder = embedder
        self._vector_store = vector_store
        self._config = config
        self._strategy = self._get_strategy()
    
    @abstractmethod
    def _get_strategy(self) -> RetrievalStrategy:
        """Get the retrieval strategy."""
        pass
    
    async def retrieve(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
        document_ids: Optional[List[UUID]] = None
    ) -> List[RetrievedChunk]:
        """Retrieve relevant chunks (implemented by subclasses)."""
        pass


class SimilarityRetriever(BaseRetriever):
    """Similarity search retriever."""
    
    def _get_strategy(self) -> RetrievalStrategy:
        return RetrievalStrategy.SIMILARITY
    
    async def retrieve(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
        document_ids: Optional[List[UUID]] = None
    ) -> List[RetrievedChunk]:
        """Retrieve chunks using similarity search."""
        try:
            # Generate query embedding
            query_embedding = await self._embedder.embed_text(query)
            
            # Build filter if document_ids specified
            filter_dict = None
            if document_ids:
                filter_dict = {
                    "document_id": {"$in": [str(doc_id) for doc_id in document_ids]}
                }
            
            # Search vector store
            results = await self._vector_store.search(
                query_embedding=query_embedding,
                namespace=namespace,
                top_k=top_k,
                filter_dict=filter_dict
            )
            
            if not results:
                logger.warning(
                    f"No results found for query in namespace {namespace} "
                    f"(strategy={self._strategy.value})"
                )
                raise NoContextFoundError(
                    "No relevant documents found for your query",
                    details={"namespace": namespace, "query": query[:100]}
                )
            
            logger.info(
                f"Retrieved {len(results)} chunks using similarity search "
                f"(namespace={namespace}, top_k={top_k})"
            )
            
            return results
            
        except NoContextFoundError:
            raise
        except Exception as e:
            logger.error(f"Similarity retrieval failed: {e}", exc_info=True)
            raise RetrievalError(
                "Failed to retrieve documents",
                details={"error": str(e), "strategy": self._strategy.value}
            )


class MMRRetriever(BaseRetriever):
    """Maximal Marginal Relevance retriever for diverse results."""
    
    def _get_strategy(self) -> RetrievalStrategy:
        return RetrievalStrategy.MMR
    
    async def retrieve(
        self,
        query: str,
        namespace: str,
        top_k: int = 5,
        document_ids: Optional[List[UUID]] = None
    ) -> List[RetrievedChunk]:
        """
        Retrieve chunks using MMR strategy.
        
        MMR optimizes for both relevance and diversity.
        """
        try:
            # Generate query embedding
            query_embedding = await self._embedder.embed_text(query)
            
            # For MMR, fetch more initial results then filter for diversity
            fetch_k = max(self._config.fetch_k, top_k * 3)
            
            # Build filter if document_ids specified
            filter_dict = None
            if document_ids:
                filter_dict = {
                    "document_id": {"$in": [str(doc_id) for doc_id in document_ids]}
                }
            
            # Get initial results
            results = await self._vector_store.search(
                query_embedding=query_embedding,
                namespace=namespace,
                top_k=fetch_k,
                filter_dict=filter_dict
            )
            
            if not results:
                logger.warning(
                    f"No results found for query in namespace {namespace} "
                    f"(strategy={self._strategy.value})"
                )
                raise NoContextFoundError(
                    "No relevant documents found for your query",
                    details={"namespace": namespace, "query": query[:100]}
                )
            
            # Apply MMR-like diversity filtering
            # Select results that maximize: relevance - lambda_mult * similarity_to_selected
            selected = []
            remaining = list(results)
            lambda_mult = self._config.lambda_mult
            
            while remaining and len(selected) < top_k:
                if not selected:
                    # First result is most relevant
                    selected.append(remaining.pop(0))
                else:
                    # Find next result that balances relevance and diversity
                    best_idx = 0
                    best_score = float('-inf')
                    
                    for i, chunk in enumerate(remaining):
                        # Relevance score
                        relevance = chunk.score
                        
                        # Diversity: minimum similarity to any selected chunk
                        diversity_penalty = 0
                        selected_texts = [s.text for s in selected]
                        for selected_chunk in selected:
                            # Approximate diversity via text overlap (simple heuristic)
                            overlap = len(set(chunk.text.split()) & set(selected_chunk.text.split()))
                            diversity_penalty = max(diversity_penalty, overlap / len(selected_chunk.text.split()))
                        
                        # MMR score
                        score = relevance - lambda_mult * diversity_penalty
                        
                        if score > best_score:
                            best_score = score
                            best_idx = i
                    
                    selected.append(remaining.pop(best_idx))
            
            logger.info(
                f"Retrieved {len(selected)} chunks using MMR strategy "
                f"(namespace={namespace}, top_k={top_k}, lambda={lambda_mult})"
            )
            
            return selected
            
        except NoContextFoundError:
            raise
        except Exception as e:
            logger.error(f"MMR retrieval failed: {e}", exc_info=True)
            raise RetrievalError(
                "Failed to retrieve documents",
                details={"error": str(e), "strategy": self._strategy.value}
            )


def create_retriever(
    strategy: RetrievalStrategy,
    embedder: IEmbedder,
    vector_store: IVectorStore,
    config: RetrieverConfig
) -> IRetriever:
    """Factory function to create retriever with specified strategy."""
    if strategy == RetrievalStrategy.SIMILARITY:
        return SimilarityRetriever(embedder, vector_store, config)
    elif strategy == RetrievalStrategy.MMR:
        return MMRRetriever(embedder, vector_store, config)
    else:
        # Default to similarity
        logger.warning(f"Unknown strategy {strategy}, using similarity")
        return SimilarityRetriever(embedder, vector_store, config)
