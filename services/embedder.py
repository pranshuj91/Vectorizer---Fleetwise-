from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """
    Manage a SentenceTransformers model and a FAISS index for document chunks.

    Embeddings and associated metadata are stored under the provided vectors_dir.
    """

    def __init__(self, vectors_dir: Path):
        self.vectors_dir = Path(vectors_dir)
        self.vectors_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.vectors_dir / "index.faiss"
        self.meta_path = self.vectors_dir / "meta.json"

        self._model: SentenceTransformer | None = None
        self._index: faiss.IndexFlatIP | None = None
        self._metadata: List[Dict[str, Any]] = []

        self._load_index_and_metadata()

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _load_model(self) -> SentenceTransformer:
        """
        Lazily load the SentenceTransformers model.
        """
        if self._model is None:
            self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._model

    def _load_index_and_metadata(self) -> None:
        """
        Load FAISS index and metadata from disk if available.
        """
        if self.index_path.exists() and self.meta_path.exists():
            # Load metadata first to infer dimensionality safely if needed
            with self.meta_path.open("r", encoding="utf-8") as f:
                self._metadata = json.load(f)

            # Load index
            self._index = faiss.read_index(str(self.index_path))
        else:
            self._metadata = []
            self._index = None

    def _save_index_and_metadata(self) -> None:
        """
        Persist the FAISS index and metadata to disk.
        """
        if self._index is None:
            return

        faiss.write_index(self._index, str(self.index_path))
        with self.meta_path.open("w", encoding="utf-8") as f:
            json.dump(self._metadata, f, ensure_ascii=False, indent=2)

    def _ensure_index(self, dim: int) -> None:
        """
        Ensure that a FAISS index exists with the given dimensionality.
        """
        if self._index is not None:
            return

        # Use inner product with normalized embeddings to emulate cosine similarity
        self._index = faiss.IndexFlatIP(dim)

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def has_index(self) -> bool:
        """
        Check if there is at least one embedding in the index.
        """
        return self._index is not None and self._index.ntotal > 0

    def add_documents(self, chunks: List[Dict[str, Any]], file_name: str) -> None:
        """
        Add a list of semantic chunks for a given file to the index.

        Each chunk is expected to have at least:
        - chunk_id: int
        - section: str
        - text: str

        The embedding input text is prefixed with rich metadata to make
        downstream retrieval more RAG-friendly.
        """
        if not chunks:
            return

        model = self._load_model()

        prepared_texts: List[str] = []
        for chunk in chunks:
            section_title = str(chunk.get("section", "Untitled"))
            text = str(chunk.get("text", ""))

            prefixed = f"Section: {section_title}\nDocument: {file_name}\n\n{text}"
            prepared_texts.append(prefixed)

        embeddings = model.encode(prepared_texts, convert_to_numpy=True, show_progress_bar=False)

        # Normalize embeddings to unit vectors
        embeddings = embeddings.astype("float32")
        faiss.normalize_L2(embeddings)

        dim = embeddings.shape[1]
        self._ensure_index(dim)

        start_id = len(self._metadata)

        self._index.add(embeddings)

        for idx, chunk in enumerate(chunks):
            self._metadata.append(
                {
                    "id": start_id + idx,
                    "file_name": file_name,
                    "chunk_index": int(chunk.get("chunk_id", idx)),
                    "section": chunk.get("section", "Untitled"),
                    "text": chunk.get("text", ""),
                }
            )

        self._save_index_and_metadata()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search the FAISS index for the most similar chunks to a query string.

        :param query: Natural language query.
        :param top_k: Number of top matches to return.
        :return: List of result dictionaries with score and metadata.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        model = self._load_model()
        query_emb = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
        query_emb = query_emb.astype("float32")
        faiss.normalize_L2(query_emb)

        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query_emb, k)

        scores_list = scores[0].tolist()
        indices_list = indices[0].tolist()

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores_list, indices_list):
            if idx < 0 or idx >= len(self._metadata):
                continue
            meta = self._metadata[idx]
            results.append(
                {
                    "score": float(score),
                    "file_name": meta["file_name"],
                    "chunk_index": meta["chunk_index"],
                    "section": meta.get("section"),
                    "page_start": meta.get("page_start"),
                    "page_end": meta.get("page_end"),
                    "text": meta["text"],
                }
            )

        return results


