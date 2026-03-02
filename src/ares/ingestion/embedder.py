"""Document embedding generation."""

import logging
from typing import List
from ares.config import settings

logger = logging.getLogger(__name__)


class DocumentEmbedder:
    """Generate embeddings for document chunks."""
    
    def __init__(self):
        """Initialize embedder with OpenAI client."""
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.openai_api_key)
            # `settings` already normalizes the value via validator, but be
            # defensive in case it comes through malformed from elsewhere.
            model = settings.embedding_model or ""
            model = model.strip().strip('"').strip("'")
            if model.startswith("openai/"):
                model = model.split("/", 1)[1]
            self.model = model
            logger.debug(f"Using embedding model '{self.model}'")
            self.batch_size = settings.embedding_batch_size
        except ImportError:
            raise ImportError("openai package required for embeddings")
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                
                logger.info(f"Embedded batch {i // self.batch_size + 1}")
            except Exception as e:
                logger.error(f"Error embedding batch: {e}")
                raise
        
        return embeddings
    
    def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        result = self.embed_texts([text])
        return result[0] if result else []
