"""Qdrant vector database client."""

import hashlib
import logging
from typing import List, Optional, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)
from ares.config import settings
from ares.schemas import DocumentChunk

logger = logging.getLogger(__name__)


class QdrantVectorDB:
    """Qdrant vector database client for document storage and retrieval."""
    
    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self.collection_name = settings.qdrant_collection
        self.vector_size = settings.vector_dim
    
    def create_collection(self, force_recreate: bool = False) -> bool:
        """
        Create collection if it doesn't exist.
        
        Args:
            force_recreate: Recreate even if exists
            
        Returns:
            True if created, False if already exists
        """
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name in collection_names:
                if force_recreate:
                    self.client.delete_collection(self.collection_name)
                    logger.info(f"Deleted existing collection: {self.collection_name}")
                else:
                    logger.info(f"Collection already exists: {self.collection_name}")
                    return False
            
            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                ),
            )

            # Create keyword payload indexes so filtered searches work
            for field in ("equipment_system", "document_type", "safety_critical"):
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )

            logger.info(f"Created collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise

    def ensure_payload_indexes(self) -> None:
        """Create payload indexes if they are missing (safe to call on existing collection)."""
        for field in ("equipment_system", "document_type", "safety_critical"):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info(f"Created payload index: {field}")
            except Exception:
                pass  # Index already exists — not an error
    
    def insert_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Insert document chunks into vector database.
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Number of chunks inserted
        """
        if not chunks:
            return 0
        
        try:
            points = []
            for idx, chunk in enumerate(chunks):
                if chunk.embedding is None:
                    logger.warning(f"Chunk {chunk.id} has no embedding, skipping")
                    continue
                
                point = PointStruct(
                    # Stable, deterministic ID across Python restarts.
                    # hash() is randomised per process (PYTHONHASHSEED), so
                    # multiple ingestion runs would create duplicates.  MD5
                    # is stable and collision-free for our chunk ID strings.
                    id=int(hashlib.md5(chunk.id.encode()).hexdigest(), 16) % (2**63),
                    vector=chunk.embedding,
                    payload={
                        "id": chunk.id,
                        "text": chunk.text,
                        "equipment_system": chunk.equipment_system,
                        "document_type": chunk.document_type,
                        "section_number": chunk.section_number,
                        "page_number": chunk.page_number,
                        "source_file": chunk.source_file,
                        "safety_critical": chunk.safety_critical,
                        "contains_warnings": chunk.contains_warnings,
                        "contains_limits": chunk.contains_limits,
                    }
                )
                points.append(point)
            
            if not points:
                logger.warning("No points with embeddings to insert")
                return 0
            
            # Upsert points (insert or update)
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"Inserted {len(points)} chunks into Qdrant")
            return len(points)
        except Exception as e:
            logger.error(f"Error inserting chunks: {e}")
            raise
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        equipment_system: Optional[str] = None,
        safety_critical_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query_vector: Query embedding vector
            limit: Number of results to return
            equipment_system: Filter by equipment system
            safety_critical_only: Only return safety-critical chunks
            
        Returns:
            List of search results with scores
        """
        try:
            # Build filter if needed
            filters = None
            if equipment_system or safety_critical_only:
                conditions = []
                
                if equipment_system:
                    conditions.append(
                        FieldCondition(
                            key="equipment_system",
                            match=MatchValue(value=equipment_system)
                        )
                    )
                
                if safety_critical_only:
                    conditions.append(
                        FieldCondition(
                            key="safety_critical",
                            match=MatchValue(value=True)
                        )
                    )
                
                if conditions:
                    filters = Filter(must=conditions)
            
            # Search — client.search() was removed in qdrant-client 1.12+
            try:
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    query_filter=filters,
                    limit=limit,
                    with_payload=True,
                )
            except Exception as filter_err:
                # Payload index missing — fall back to unfiltered search so
                # the researcher agent always gets real results.
                if filters is not None and "Index required" in str(filter_err):
                    logger.warning(
                        "Payload index missing for filter; falling back to unfiltered search. "
                        "Run `ensure_payload_indexes()` to fix permanently."
                    )
                    response = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=None,
                        limit=limit,
                        with_payload=True,
                    )
                else:
                    raise

            # Format results
            formatted = []
            for result in response.points:
                formatted.append({
                    "id": result.payload.get("id"),
                    "text": result.payload.get("text"),
                    "score": result.score,
                    "source_file": result.payload.get("source_file"),
                    "page_number": result.payload.get("page_number"),
                    "safety_critical": result.payload.get("safety_critical"),
                })

            return formatted
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dictionary with collection stats
        """
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vector_size": info.config.params.vectors.size,
                "distance": str(info.config.params.vectors.distance),
                "points_count": info.points_count,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
