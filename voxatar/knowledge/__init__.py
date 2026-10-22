# Knowledge management (RAG) for Voxatar

"""RAG pipeline and document manager using ChromaDB + Ollama embeddings."""

from voxatar.knowledge.rag import RAGPipeline
from voxatar.knowledge.manager import KnowledgeBaseManager

__all__ = ["RAGPipeline", "KnowledgeBaseManager"]