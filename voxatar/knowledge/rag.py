from __future__ import annotations

"""
RAG pipeline using ChromaDB for vector storage and Ollama for embeddings.

Provides document chunking, embedding, ingestion, and semantic retrieval.
"""

import logging
import uuid
from typing import Any

import chromadb
import httpx

logger = logging.getLogger(__name__)

# Ollama embedding model
EMBEDDING_MODEL = "nomic-embed-text"


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline.

    Uses ChromaDB (PersistentClient) for vector storage and Ollama's
    /api/embeddings endpoint with nomic-embed-text for embeddings.
    """

    def __init__(
        self,
        collection_name: str = "voxatar_kb",
        persist_dir: str = "/app/data/chromadb",
        ollama_url: str = "http://host.docker.internal:11434",
    ) -> None:
        """
        Initialize the RAG pipeline.

        Args:
            collection_name: ChromaDB collection name.
            persist_dir: Directory for ChromaDB persistent storage.
            ollama_url: Base URL for the Ollama API.
        """
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.ollama_url = ollama_url.rstrip("/")
        self._embeddings_endpoint = f"{self.ollama_url}/api/embeddings"

        # Initialize ChromaDB client and collection
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "RAGPipeline initialised: collection=%s, persist_dir=%s",
            collection_name,
            persist_dir,
        )

    # ------------------------------------------------------------------ #
    #  Embedding                                                         #
    # ------------------------------------------------------------------ #

    async def embed(self, text: str) -> list[float]:
        """
        Get embeddings for a text string from the Ollama API.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            RuntimeError: If the embedding API call fails.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._embeddings_endpoint,
                    json={"model": EMBEDDING_MODEL, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding")
                if embedding is None:
                    raise RuntimeError("No 'embedding' field in Ollama response")
                return embedding
        except httpx.HTTPError as e:
            logger.error("Embedding HTTP error: %s", e)
            raise RuntimeError(f"Embedding request failed: {e}") from e
        except Exception as e:
            logger.error("Embedding error: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Chunking                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def chunk_document(
        text: str,
        chunk_size: int = 500,
        overlap: int = 100,
    ) -> list[str]:
        """
        Split text into overlapping word-based chunks.

        Args:
            text: The document text to chunk.
            chunk_size: Number of words per chunk.
            overlap: Number of words to overlap between chunks.

        Returns:
            A list of chunk strings.
        """
        words = text.split()
        if not words:
            return []

        chunks: list[str] = []
        step = max(1, chunk_size - overlap)
        for start in range(0, len(words), step):
            chunk_words = words[start : start + chunk_size]
            chunk = " ".join(chunk_words)
            chunks.append(chunk)
            if start + chunk_size >= len(words):
                break
        return chunks

    # ------------------------------------------------------------------ #
    #  Ingestion                                                         #
    # ------------------------------------------------------------------ #

    async def ingest_document(
        self,
        doc_id: str,
        filename: str,
        content: str,
        content_type: str,
    ) -> int:
        """
        Chunk, embed, and store a document in ChromaDB.

        Args:
            doc_id: Unique document identifier.
            filename: Original filename.
            content: Full text content of the document.
            content_type: MIME type (e.g. "text/plain", "application/pdf").

        Returns:
            Number of chunks stored.
        """
        chunks = self.chunk_document(content)
        if not chunks:
            logger.warning("No chunks produced for document %s", doc_id)
            return 0

        # Embed all chunks
        embeddings: list[list[float]] = []
        for chunk in chunks:
            embedding = await self.embed(chunk)
            embeddings.append(embedding)

        # Generate IDs and metadata for each chunk
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": filename,
                "content_type": content_type,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]

        # Store in ChromaDB
        self._collection.add(
            ids=chunk_ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            "Ingested document %s: %d chunks into collection %s",
            doc_id,
            len(chunks),
            self.collection_name,
        )
        return len(chunks)

    # ------------------------------------------------------------------ #
    #  Retrieval                                                         #
    # ------------------------------------------------------------------ #

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embed a query and retrieve the top-k matching chunks.

        Args:
            query: The search query.
            top_k: Number of results to return.

        Returns:
            A list of dicts with keys: text, score, metadata.
        """
        query_embedding = await self.embed(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])

        output: list[dict[str, Any]] = []
        for i, doc in enumerate(documents[0] if documents else []):
            distance = distances[0][i] if distances and len(distances[0]) > i else 1.0
            score = 1.0 - distance  # Convert cosine distance to similarity
            output.append(
                {
                    "text": doc,
                    "score": score,
                    "metadata": metadatas[0][i] if metadatas and len(metadatas[0]) > i else {},
                }
            )
        return output

    async def get_context_for_prompt(
        self,
        query: str,
        top_k: int = 5,
    ) -> str:
        """
        Retrieve relevant chunks and format them as a context string.

        Args:
            query: The search query.
            top_k: Number of chunks to retrieve.

        Returns:
            A formatted context string suitable for injection into an LLM prompt.
        """
        results = await self.retrieve(query, top_k=top_k)
        if not results:
            return ""

        context_parts: list[str] = []
        for i, result in enumerate(results, 1):
            source = result["metadata"].get("filename", "unknown")
            context_parts.append(
                f"[{i}] (Source: {source})\n{result['text']}"
            )
        return "\n\n".join(context_parts)