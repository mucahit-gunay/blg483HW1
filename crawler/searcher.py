"""
Search engine with hand-rolled TF-IDF relevance scoring.
Queries the SQLite database directly so new pages appear in results immediately,
even while indexing is still active.
"""

import math
import re
from collections import Counter
from typing import Optional

from crawler.storage import Storage


# Common English stop words to ignore in scoring
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "it", "its", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they", "me", "him",
    "her", "us", "them", "my", "your", "his", "our", "their", "what",
    "which", "who", "whom", "not", "no", "so", "if", "as", "from",
    "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "up", "down", "then", "than",
}


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering stop words."""
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def compute_tf(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency (normalized by document length)."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {term: count / total for term, count in counts.items()}


class Searcher:
    """TF-IDF based search over indexed pages."""

    def __init__(self, storage: Storage):
        self.storage = storage

    async def search(self, query: str, limit: int = 50) -> list[dict]:
        """
        Search indexed pages for relevance to query.
        Returns list of triples: (relevant_url, origin_url, depth)
        with additional metadata (title, score).

        Uses a two-phase approach:
        1. Pre-filter: SQLite LIKE to narrow candidates (fast)
        2. Rank: TF-IDF scoring on candidates (accurate)
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        # Phase 1: pre-filter with SQL LIKE
        candidates = await self.storage.search_pages(query)
        if not candidates:
            return []

        # Phase 2: TF-IDF ranking
        # Compute IDF across candidate set
        doc_count = len(candidates)
        term_doc_counts: dict[str, int] = Counter()

        doc_data = []
        for doc in candidates:
            text = f"{doc.get('title', '')} {doc.get('content', '')}"
            tokens = tokenize(text)
            tf = compute_tf(tokens)
            unique_terms = set(tokens)
            for term in query_tokens:
                if term in unique_terms:
                    term_doc_counts[term] += 1
            doc_data.append((doc, tf))

        # Compute IDF
        idf = {}
        for term in query_tokens:
            df = term_doc_counts.get(term, 0)
            idf[term] = math.log((doc_count + 1) / (df + 1)) + 1  # Smoothed IDF

        # Score each document
        scored = []
        for doc, tf in doc_data:
            score = 0.0
            for term in query_tokens:
                tf_val = tf.get(term, 0.0)
                idf_val = idf.get(term, 0.0)
                score += tf_val * idf_val

            # Boost score if query appears in title
            title_lower = doc.get("title", "").lower()
            for term in query_tokens:
                if term in title_lower:
                    score *= 1.5

            scored.append((score, doc))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Format results as triples + metadata
        results = []
        for score, doc in scored[:limit]:
            if score > 0:
                results.append({
                    "relevant_url": doc["url"],
                    "origin_url": doc["origin"],
                    "depth": doc["depth"],
                    "title": doc.get("title", ""),
                    "score": round(score, 4),
                })

        return results

    async def search_by_frequency(self, query: str, limit: int = 50) -> list[dict]:
        """
        Search using the homework scoring formula:
        score = (frequency × 10) + 1000 (exact match bonus) - (depth × 5)

        For multi-word queries, scores are summed per URL.
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            # If all words are stop words, use raw query terms
            query_tokens = [w.lower() for w in query.split() if len(w) > 1]
        if not query_tokens:
            return []

        # Collect scores per URL
        url_scores: dict[str, dict] = {}

        for term in query_tokens:
            entries = await self.storage.search_by_word(term, limit=500)
            for entry in entries:
                url = entry["url"]
                freq = entry["frequency"]
                depth = entry["depth"]

                # Exact match bonus: word matches query term exactly
                exact_bonus = 1000 if entry["word"] == term else 0
                score = (freq * 10) + exact_bonus - (depth * 5)

                if url not in url_scores:
                    url_scores[url] = {
                        "url": url,
                        "origin": entry["origin"],
                        "depth": depth,
                        "relevance_score": 0,
                    }
                url_scores[url]["relevance_score"] += score

        # Sort by relevance_score descending
        results = sorted(url_scores.values(), key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]

