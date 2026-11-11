"""Hybrid retrieval for Axiom (PRD §4.3 A-10; I1.4).

Implements:
- BM25 (rank_bm25) lexical retrieval over the in-memory source corpus.
- Vector KNN exact search using cosine similarity (no ANN — corpus is small,
  full recall required; tenant filtering applied before ranking).
- Reciprocal Rank Fusion (RRF, k=60) to merge BM25 and vector ranks.
- Tenant-scoped queries: only sources belonging to the calling tenant are searched.
- Retrieval trace: each result carries which sources matched BM25, vector, or both.

No external network calls are made. Embeddings are computed with the same
deterministic 384-d local function used by the GuidelineCompiler.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from rank_bm25 import BM25Okapi
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SourceRecord:
    """A single knowledge-base source record for retrieval."""
    source_id: str
    version: int
    tenant_id: str
    kind: str          # "rule" | "fact" | "glossary" | "palette"
    body: str          # human-readable text used for BM25 and display
    embedding: Optional[List[float]] = None   # 384-d vector; None = not compiled


@dataclass
class RetrievalHit:
    """A single ranked hit from the hybrid retrieval."""
    source_id: str
    version: int
    kind: str
    body: str
    rrf_score: float
    bm25_rank: Optional[int] = None   # 1-based BM25 rank; None if not in BM25 top-k
    vector_rank: Optional[int] = None # 1-based vector rank; None if not in vector top-k
    bm25_score: float = 0.0
    vector_score: float = 0.0

    @property
    def trace(self) -> str:
        """Human-readable trace string for Unsupported receipts."""
        parts = []
        if self.bm25_rank is not None:
            parts.append(f"BM25 rank={self.bm25_rank} score={self.bm25_score:.4f}")
        if self.vector_rank is not None:
            parts.append(f"vector rank={self.vector_rank} score={self.vector_score:.4f}")
        method = "BM25+vector(RRF)" if (self.bm25_rank and self.vector_rank) else (
            "BM25-only" if self.bm25_rank else "vector-only"
        )
        return f"{self.source_id}@v{self.version} [{method}] rrf={self.rrf_score:.4f} | " + " | ".join(parts)


@dataclass
class RetrievalResult:
    """The full output of a hybrid retrieval query."""
    query: str
    tenant_id: str
    hits: List[RetrievalHit] = field(default_factory=list)
    top_k: int = 5

    @property
    def trace_lines(self) -> List[str]:
        """Return one trace string per hit for embedding in findings / receipts."""
        return [h.trace for h in self.hits[:self.top_k]]

    @property
    def trace_summary(self) -> str:
        """Single-line trace summary suitable for the explanation field."""
        if not self.hits:
            return "No candidates found in tenant KB."
        return f"Searched {self.tenant_id} KB; top candidates: " + ", ".join(
            f"{h.source_id}@v{h.version}(rrf={h.rrf_score:.3f})"
            for h in self.hits[:self.top_k]
        )


# ---------------------------------------------------------------------------
# Local 384-d embedding (matches GuidelineCompiler's deterministic function)
# ---------------------------------------------------------------------------

def _embed(text: str) -> List[float]:
    """Deterministic 384-d L2-normalised embedding (100 % local, no network)."""
    import hashlib
    cleaned = text.lower().strip()
    vector = [0.0] * 384
    words = re.findall(r"\w+", cleaned) or ["empty"]
    for word_idx, word in enumerate(words):
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        for dim in range(384):
            val = ((h >> (dim % 64)) & 0xFF) / 255.0 - 0.5
            vector[dim] += val / (1.0 + math.log1p(word_idx))
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [round(x / norm, 6) for x in vector]
    else:
        vector[0] = 1.0
    return vector


def _cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two L2-normalised vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    # Already normalised, so ||a||=||b||=1; clamp numerical drift
    return min(1.0, max(-1.0, dot))


# ---------------------------------------------------------------------------
# RRF fusion
# ---------------------------------------------------------------------------

RRF_K = 60  # PRD §4.3 A-10


def _rrf_score(rank: int, k: int = RRF_K) -> float:
    """Reciprocal Rank Fusion contribution: 1/(k + rank)."""
    return 1.0 / (k + rank)


# ---------------------------------------------------------------------------
# HybridRetriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """Tenant-scoped hybrid BM25 + exact-KNN retriever with RRF fusion.

    Usage::

        retriever = HybridRetriever()
        retriever.add_source(SourceRecord(...))
        result = retriever.query("10,000 customers", tenant_id="tenant_meridian", top_k=5)
        for hit in result.hits:
            print(hit.trace)
    """

    def __init__(self) -> None:
        # Per-tenant BM25 state
        self._tenant_corpus: Dict[str, List[Tuple[str, int, List[str]]]] = {}
        # (source_id, version, tokens)
        self._tenant_bm25: Dict[str, Optional[BM25Okapi]] = {}  # type: ignore[type-arg]

        # All records indexed by (source_id, version) for vector search
        self._records: Dict[Tuple[str, int], SourceRecord] = {}

    # ------------------------------------------------------------------
    # Corpus management
    # ------------------------------------------------------------------

    def add_source(self, record: SourceRecord) -> None:
        """Add (or replace) a source record in the retriever corpus.

        Embeddings are computed automatically if not already present.
        """
        if record.embedding is None:
            record.embedding = _embed(f"{record.source_id} {record.body}")

        key = (record.source_id, record.version)
        self._records[key] = record

        # Rebuild BM25 for this tenant
        tenant = record.tenant_id
        # Remove old entry for this (source_id, version) if present
        existing = [(sid, ver, toks) for sid, ver, toks in self._tenant_corpus.get(tenant, [])
                    if not (sid == record.source_id and ver == record.version)]
        tokens = re.findall(r"\w+", f"{record.source_id} {record.body}".lower())
        existing.append((record.source_id, record.version, tokens))
        self._tenant_corpus[tenant] = existing
        self._rebuild_bm25(tenant)

    def _rebuild_bm25(self, tenant_id: str) -> None:
        corpus = self._tenant_corpus.get(tenant_id, [])
        if not corpus:
            self._tenant_bm25[tenant_id] = None
            return
        tokenized = [toks for _, _, toks in corpus]
        self._tenant_bm25[tenant_id] = BM25Okapi(tokenized) if _HAS_BM25 else None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        query_text: str,
        tenant_id: str,
        top_k: int = 5,
        session: Optional[Any] = None,
    ) -> RetrievalResult:
        """Execute hybrid BM25 + vector KNN with RRF fusion, tenant-scoped.

        Args:
            query_text: The claim or phrase to retrieve supporting sources for.
            tenant_id: Only records for this tenant are searched.
            top_k: Number of hits to return after RRF fusion.
            session: Optional DB session for pgvector exact KNN execution.

        Returns:
            RetrievalResult with ranked hits and retrieval traces.
        """
        result = RetrievalResult(query=query_text, tenant_id=tenant_id, top_k=top_k)

        # Tenant-scoped records
        tenant_records = [r for r in self._records.values() if r.tenant_id == tenant_id]
        if not tenant_records:
            return result

        query_tokens = re.findall(r"\w+", query_text.lower()) or ["empty"]
        query_embedding = _embed(query_text)

        # --- BM25 ---
        bm25_ranked: Dict[Tuple[str, int], Tuple[int, float]] = {}  # key -> (rank, score)
        corpus_entries = self._tenant_corpus.get(tenant_id, [])
        bm25_index = self._tenant_bm25.get(tenant_id)

        if bm25_index and corpus_entries:
            scores = bm25_index.get_scores(query_tokens)
            ranked = sorted(
                [(corpus_entries[i][0], corpus_entries[i][1], scores[i])
                 for i in range(len(scores))],
                key=lambda x: x[2], reverse=True,
            )
            for rank_0, (sid, ver, score) in enumerate(ranked):
                bm25_ranked[(sid, ver)] = (rank_0 + 1, score)

        # --- Vector exact KNN ---
        vector_ranked: Dict[Tuple[str, int], Tuple[int, float]] = {}
        
        # If DB session is provided, execute pgvector exact KNN in DB (no ANN; full recall)
        if session is not None:
            try:
                from sqlalchemy import select
                from api.src.models.source import SourceVersion
                stmt = (
                    select(SourceVersion)
                    .where(SourceVersion.tenant_id == tenant_id)
                    .where(SourceVersion.embedding.isnot(None))
                    .order_by(SourceVersion.embedding.cosine_distance(query_embedding))
                    .limit(top_k * 5)
                )
                db_rows = session.execute(stmt).scalars().all()
                if db_rows:
                    for rank_0, sv in enumerate(db_rows):
                        vector_ranked[(sv.source_id, sv.version)] = (rank_0 + 1, 1.0)
            except Exception:
                vector_ranked.clear()

        # In-memory exact KNN if vector_ranked is empty
        if not vector_ranked:
            cosine_scores = []
            for rec in tenant_records:
                if rec.embedding:
                    sim = _cosine(query_embedding, rec.embedding)
                    cosine_scores.append((rec.source_id, rec.version, sim))

            cosine_scores.sort(key=lambda x: x[2], reverse=True)
            for rank_0, (sid, ver, sim) in enumerate(cosine_scores):
                vector_ranked[(sid, ver)] = (rank_0 + 1, sim)

        # --- RRF fusion ---
        all_keys = set(bm25_ranked.keys()) | set(vector_ranked.keys())
        rrf_scores: Dict[Tuple[str, int], float] = {}
        for key in all_keys:
            score = 0.0
            if key in bm25_ranked:
                score += _rrf_score(bm25_ranked[key][0])
            if key in vector_ranked:
                score += _rrf_score(vector_ranked[key][0])
            rrf_scores[key] = score

        # Sort by RRF descending and build hits
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        for key in sorted_keys[:top_k]:
            sid, ver = key
            rec = self._records.get(key)
            if rec is None:
                continue
            b_rank, b_score = bm25_ranked.get(key, (None, 0.0))
            v_rank, v_score = vector_ranked.get(key, (None, 0.0))
            result.hits.append(
                RetrievalHit(
                    source_id=sid,
                    version=ver,
                    kind=rec.kind,
                    body=rec.body,
                    rrf_score=rrf_scores[key],
                    bm25_rank=b_rank,
                    vector_rank=v_rank,
                    bm25_score=b_score,
                    vector_score=v_score,
                )
            )

        return result


# ---------------------------------------------------------------------------
# Global default retriever (pre-seeded from brand_kit fixtures)
# ---------------------------------------------------------------------------

def _build_default_retriever() -> HybridRetriever:
    """Build a default HybridRetriever pre-loaded with Meridian Flow brand kit sources."""
    from brand_kit.fixtures import FACTS, GLOSSARY, RULES

    retriever = HybridRetriever()
    tenant = "tenant_meridian"

    for rule in RULES:
        retriever.add_source(SourceRecord(
            source_id=rule.rule_id,
            version=1,
            tenant_id=tenant,
            kind="rule",
            body=f"{rule.title}. {rule.description}",
        ))

    for term in GLOSSARY:
        body_parts = [f"preferred: {term.preferred}"]
        if term.banned:
            body_parts.append(f"banned: {', '.join(term.banned)}")
        if term.notes:
            body_parts.append(term.notes)
        retriever.add_source(SourceRecord(
            source_id=term.term_id,
            version=1,
            tenant_id=tenant,
            kind="glossary",
            body=" | ".join(body_parts),
        ))

    for fact in FACTS:
        # Index each version separately so source_id@version resolves
        for fv in fact.versions:
            valid_from_str = fv.valid_from.isoformat() if fv.valid_from else "unknown"
            valid_until_str = f" to {fv.valid_until.isoformat()}" if fv.valid_until else ""
            unit_str = f" {fv.unit}" if getattr(fv, "unit", None) else ""
            body = f"{fact.subject}: {fv.value}{unit_str} (valid from {valid_from_str}{valid_until_str})"
            retriever.add_source(SourceRecord(
                source_id=fact.fact_id,
                version=fv.version,
                tenant_id=tenant,
                kind="fact",
                body=body,
            ))

    return retriever


_DEFAULT_RETRIEVER: Optional[HybridRetriever] = None


def get_default_retriever() -> HybridRetriever:
    """Return (and lazily init) the global default retriever."""
    global _DEFAULT_RETRIEVER
    if _DEFAULT_RETRIEVER is None:
        _DEFAULT_RETRIEVER = _build_default_retriever()
    return _DEFAULT_RETRIEVER

