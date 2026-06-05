"""
ICD-10 Code Search Service using BM25 + keyword matching
Anti-hallucination: ALL returned codes are verified to exist in the database
"""
import re
import logging
from rank_bm25 import BM25Okapi
from data.icd10_data import ICD10_CODES, get_all_keywords, get_code_by_id

logger = logging.getLogger(__name__)


class ICDService:
    def __init__(self):
        self._build_index()

    def _build_index(self):
        """Build BM25 search index over all ICD-10 codes."""
        self.codes = ICD10_CODES
        self.corpus_texts = get_all_keywords()

        # Tokenize for BM25
        tokenized = [self._tokenize(doc) for doc in self.corpus_texts]
        self.bm25 = BM25Okapi(tokenized)
        logger.info(f"ICD-10 index built: {len(self.codes)} codes")

    def _tokenize(self, text: str) -> list:
        """Tokenize text, preserving medical abbreviations."""
        text = text.lower()
        # Keep alphanumeric and dots (for codes like E11.9)
        tokens = re.findall(r'[a-z0-9]+(?:\.[a-z0-9]+)?', text)
        return tokens

    def search(self, query: str, top_k: int = 25) -> list:
        """
        Search for ICD-10 codes matching a clinical query.
        Returns list of code dicts with 'score' field added.
        All returned codes are VERIFIED to exist in the database.
        """
        if not query or not query.strip():
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Get top results
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        seen_codes = set()

        for idx, score in indexed:
            if len(results) >= top_k:
                break
            if score <= 0:
                continue
            code_entry = self.codes[idx].copy()
            if code_entry["code"] not in seen_codes:
                code_entry["bm25_score"] = float(score)
                results.append(code_entry)
                seen_codes.add(code_entry["code"])

        return results

    def search_multi(self, queries: list, top_k: int = 30) -> list:
        """Search with multiple queries, merge and deduplicate results."""
        seen = {}
        for q in queries:
            for r in self.search(q, top_k=15):
                code = r["code"]
                if code not in seen or r["bm25_score"] > seen[code]["bm25_score"]:
                    seen[code] = r

        # Sort by score
        results = sorted(seen.values(), key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_k]

    def validate_code(self, code: str) -> dict | None:
        """Validate a code exists in the database. Returns entry or None."""
        return get_code_by_id(code)

    def get_code_description(self, code: str) -> str:
        entry = get_code_by_id(code)
        return entry["description"] if entry else "Unknown code"

    def filter_valid_codes(self, codes: list) -> list:
        """Filter a list of code strings to only those that exist in our DB."""
        valid = []
        for c in codes:
            entry = self.validate_code(c)
            if entry:
                valid.append(entry)
        return valid
