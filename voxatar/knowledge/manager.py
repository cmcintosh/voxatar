from __future__ import annotations

"""
Knowledge Base Manager.

Handles document upload, text extraction (PDF, DOCX, TXT/MD), metadata
tracking, and deletion. Delegates vector storage to RAGPipeline.
"""

import json
import logging
import os
import uuid
from typing import Any

from voxatar.knowledge.rag import RAGPipeline

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """
    Manages document lifecycle: upload → extract text → ingest into RAG.

    Document metadata is persisted in a JSON file at ``storage_dir/metadata.json``.
    """

    def __init__(
        self,
        rag: RAGPipeline,
        storage_dir: str = "/app/data/documents",
    ) -> None:
        """
        Initialize the manager.

        Args:
            rag: The RAGPipeline instance for vector storage.
            storage_dir: Directory to store uploaded document files.
        """
        self.rag = rag
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._metadata_path = os.path.join(self.storage_dir, "metadata.json")
        logger.info("KnowledgeBaseManager initialised: storage_dir=%s", storage_dir)

    # ------------------------------------------------------------------ #
    #  Upload                                                            #
    # ------------------------------------------------------------------ #

    async def upload_document(
        self,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        """
        Save a file, extract text, and ingest it into the RAG pipeline.

        Args:
            filename: Original filename.
            content: Raw file bytes.
            content_type: MIME type (e.g. "application/pdf", "text/plain").

        Returns:
            Dict with: id, filename, size, chunks, content_type.
        """
        doc_id = str(uuid.uuid4())

        # Save the raw file
        file_path = os.path.join(self.storage_dir, f"{doc_id}_{filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        file_size = len(content)

        # Extract text based on content type
        text = self._extract_text(content, content_type, filename)

        if not text.strip():
            logger.warning("No text extracted from %s (type=%s)", filename, content_type)
            # Clean up the file if no text was extracted
            os.remove(file_path)
            return {
                "id": doc_id,
                "filename": filename,
                "size": file_size,
                "chunks": 0,
                "content_type": content_type,
                "error": "No text could be extracted from the document",
            }

        # Ingest into RAG
        chunk_count = await self.rag.ingest_document(
            doc_id=doc_id,
            filename=filename,
            content=text,
            content_type=content_type,
        )

        # Save metadata
        doc_meta = {
            "id": doc_id,
            "filename": filename,
            "size": file_size,
            "chunks": chunk_count,
            "content_type": content_type,
            "file_path": file_path,
        }
        self._append_metadata(doc_meta)

        logger.info(
            "Uploaded document %s: %d bytes, %d chunks",
            filename,
            file_size,
            chunk_count,
        )
        return doc_meta

    # ------------------------------------------------------------------ #
    #  Listing & info                                                    #
    # ------------------------------------------------------------------ #

    def list_documents(self) -> list[dict[str, Any]]:
        """List all uploaded documents from the metadata file."""
        return self._load_metadata()

    def get_document_info(self, doc_id: str) -> dict[str, Any] | None:
        """Return metadata for a single document, or None if not found."""
        for doc in self._load_metadata():
            if doc.get("id") == doc_id:
                return doc
        return None

    # ------------------------------------------------------------------ #
    #  Deletion                                                          #
    # ------------------------------------------------------------------ #

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove a document from ChromaDB, delete its file, and update metadata.

        Returns:
            True if the document was found and deleted, False otherwise.
        """
        docs = self._load_metadata()
        target = None
        remaining: list[dict[str, Any]] = []
        for doc in docs:
            if doc.get("id") == doc_id:
                target = doc
            else:
                remaining.append(doc)

        if target is None:
            return False

        # Remove from ChromaDB — delete all chunk IDs for this doc
        # ChromaDB supports filtering by metadata
        try:
            self.rag._collection.delete(where={"doc_id": doc_id})
        except Exception as e:
            logger.warning("ChromaDB deletion error for doc %s: %s", doc_id, e)

        # Delete the file
        file_path = target.get("file_path")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        # Update metadata file
        self._save_metadata(remaining)

        logger.info("Deleted document %s", doc_id)
        return True

    # ------------------------------------------------------------------ #
    #  Text extraction                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_text(
        content: bytes,
        content_type: str,
        filename: str,
    ) -> str:
        """
        Extract plain text from file bytes based on content type.

        Supports: PDF (pypdf), DOCX (python-docx), TXT/MD (direct decode).
        """
        # Determine type by extension if content_type is generic
        lower_name = filename.lower()

        try:
            if content_type == "application/pdf" or lower_name.endswith(".pdf"):
                from pypdf import PdfReader
                from io import BytesIO

                reader = PdfReader(BytesIO(content))
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)

            elif (
                content_type
                in (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/msword",
                )
                or lower_name.endswith(".docx")
                or lower_name.endswith(".doc")
            ):
                from docx import Document as DocxDocument
                from io import BytesIO

                doc = DocxDocument(BytesIO(content))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return "\n\n".join(paragraphs)

            else:
                # Treat as text / markdown
                return content.decode("utf-8", errors="replace")

        except ImportError as e:
            logger.error("Missing dependency for text extraction: %s", e)
            raise RuntimeError(f"Required library not installed: {e}") from e
        except Exception as e:
            logger.error("Text extraction failed for %s: %s", filename, e)
            return ""

    # ------------------------------------------------------------------ #
    #  Metadata persistence                                              #
    # ------------------------------------------------------------------ #

    def _load_metadata(self) -> list[dict[str, Any]]:
        """Load the metadata list from the JSON file."""
        if not os.path.exists(self._metadata_path):
            return []
        try:
            with open(self._metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load metadata: %s", e)
            return []

    def _save_metadata(self, docs: list[dict[str, Any]]) -> None:
        """Overwrite the metadata file."""
        with open(self._metadata_path, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)

    def _append_metadata(self, doc_meta: dict[str, Any]) -> None:
        """Append a single document to the metadata file."""
        docs = self._load_metadata()
        docs.append(doc_meta)
        self._save_metadata(docs)