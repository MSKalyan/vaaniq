"""Deterministic local embedding provider.

Implements `EmbeddingProvider` without any external service, so knowledge-base
retrieval works in development and tests with no API keys and no network.

This is a hashed bag-of-features encoder (word unigrams + bigrams + character
3-grams), L2-normalized into `dimension` buckets. It is NOT a semantic model —
it gives exact lexical matching, which is enough for tests and offline demos.
Set EMBEDDING_PROVIDER=openai for real semantic retrieval.
"""

import hashlib
import math
import re
from collections import Counter

from app.integrations.base import EmbeddingProvider

_TOKEN_RE = re.compile(r"[a-z0-9]+")
DEFAULT_DIMENSION = 256


class HashingEmbedding(EmbeddingProvider):
    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for feature, count in _features(text).items():
            index = _bucket(feature, self._dimension)
            vector[index] += count
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


def _features(text: str) -> Counter[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    features: Counter[str] = Counter(tokens)
    for first, second in zip(tokens, tokens[1:], strict=False):
        features[f"{first}_{second}"] += 1
    joined = "".join(tokens)
    for i in range(len(joined) - 2):
        features[f"#{joined[i : i + 3]}"] += 1
    return features


def _bucket(feature: str, dimension: int) -> int:
    digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimension
