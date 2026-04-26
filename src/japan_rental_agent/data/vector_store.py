from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

import chromadb
from openai import OpenAI

from japan_rental_agent.config import AppConfig


@dataclass(slots=True)
class SeedRecord:
    id: str
    document: str
    metadata: dict[str, Any]


class TextEmbedderProtocol(Protocol):
    name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...

    def describe(self) -> dict[str, Any]: ...


class DeterministicTextEmbedder:
    """Stable local embedding fallback for development and offline seeding."""

    name = "deterministic-hash"

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return tokens or ["empty"]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in self._tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, len(digest), 2):
                index = int.from_bytes(digest[offset : offset + 2], "big") % self.dimension
                sign = 1.0 if digest[offset] % 2 == 0 else -1.0
                vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def describe(self) -> dict[str, Any]:
        return {
            "embedding_backend": self.name,
            "embedding_dimension": self.dimension,
        }


class OpenAICompatibleTextEmbedder:
    """Embedding client for OpenAI-compatible providers such as Gemini's OpenAI endpoint."""

    name = "openai-compatible"

    def __init__(self, config: AppConfig) -> None:
        if not config.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required for OpenAI-compatible embeddings.")
        if not config.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is required for OpenAI-compatible embeddings.")
        if not config.llm_embedding_model:
            raise RuntimeError("LLM_EMBEDDING_MODEL is required for OpenAI-compatible embeddings.")

        self.client = OpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
        self.model_name = config.llm_embedding_model
        self.dimension = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model_name, input=texts)
        embeddings = [list(item.embedding) for item in response.data]
        if embeddings:
            self.dimension = len(embeddings[0])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        embeddings = self.embed_documents([text])
        return embeddings[0]

    def describe(self) -> dict[str, Any]:
        return {
            "embedding_backend": self.name,
            "embedding_model": self.model_name,
            "embedding_dimension": self.dimension,
        }


class ResilientTextEmbedder:
    """Uses the live embedding endpoint when possible and falls back to a stable local embedder."""

    def __init__(self, primary: TextEmbedderProtocol, fallback: TextEmbedderProtocol) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = f"{primary.name}|fallback:{fallback.name}"
        self.dimension = getattr(primary, "dimension", 0) or getattr(fallback, "dimension", 0)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            embeddings = self.primary.embed_documents(texts)
            if embeddings:
                self.dimension = len(embeddings[0])
            return embeddings
        except Exception:
            embeddings = self.fallback.embed_documents(texts)
            self.dimension = len(embeddings[0]) if embeddings else self.dimension
            return embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            embedding = self.primary.embed_query(text)
            self.dimension = len(embedding)
            return embedding
        except Exception:
            embedding = self.fallback.embed_query(text)
            self.dimension = len(embedding)
            return embedding

    def describe(self) -> dict[str, Any]:
        primary = self.primary.describe()
        fallback = self.fallback.describe()
        return {
            "embedding_backend": self.name,
            "primary_backend": primary.get("embedding_backend", getattr(self.primary, "name", "unknown")),
            "fallback_backend": fallback.get("embedding_backend", getattr(self.fallback, "name", "unknown")),
            "embedding_model": primary.get("embedding_model"),
            "embedding_dimension": self.dimension or fallback.get("embedding_dimension"),
        }


def create_text_embedder(config: AppConfig) -> TextEmbedderProtocol:
    fallback = DeterministicTextEmbedder()
    if config.llm_api_key and config.llm_base_url and config.llm_embedding_model:
        try:
            return ResilientTextEmbedder(OpenAICompatibleTextEmbedder(config), fallback)
        except Exception:
            return fallback
    return fallback


class ChromaVectorStore:
    """Persistent local Chroma wrapper used for seeding and semantic lookups."""

    def __init__(self, config: AppConfig, embedder: TextEmbedderProtocol | None = None) -> None:
        self.config = config
        self.embedder = embedder or create_text_embedder(config)
        self.config.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.config.chroma_dir))

    def get_or_create_collection(self, name: str, metadata: dict[str, Any] | None = None):
        kwargs: dict[str, Any] = {
            "name": name,
            "embedding_function": None,
        }
        if metadata:
            kwargs["metadata"] = metadata
        return self.client.get_or_create_collection(**kwargs)

    def reset_collection(self, name: str) -> None:
        existing_names = {collection.name for collection in self.client.list_collections()}
        if name in existing_names:
            self.client.delete_collection(name)

    def upsert_records(
        self,
        collection_name: str,
        records: list[SeedRecord],
        *,
        reset: bool = False,
        batch_size: int = 64,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if reset:
            self.reset_collection(collection_name)

        collection_metadata = dict(metadata or {})
        collection_metadata.update(self.embedder.describe())
        collection = self.get_or_create_collection(collection_name, metadata=collection_metadata)

        inserted = 0
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            ids = [record.id for record in batch]
            documents = [record.document for record in batch]
            metadatas = [record.metadata for record in batch]
            embeddings = self.embedder.embed_documents(documents)
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            inserted += len(batch)
        return inserted

    def similarity_search(
        self,
        *,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        collection = self.get_or_create_collection(collection_name)
        query_embedding = self.embedder.embed_query(query_text)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )
