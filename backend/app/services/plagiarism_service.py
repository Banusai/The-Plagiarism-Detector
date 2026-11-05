from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

import faiss
import numpy as np

from app.core.config import DEFAULT_THRESHOLD, FINAL_TOP_N, TOP_K
from app.schemas.plagiarism import MatchResult, PlagiarismCheckResponse
from app.services.chunking import chunk_text
from app.services.corpus_indexer import ChunkRecord, load_index
from app.services.embedder import encode_texts


@dataclass
class RawMatch:
    document_id: str
    filename: str
    similarity_score: float
    matched_text: str
    highlighted_match: str
    input_chunk: str


def highlight_overlap(source_text: str, query_text: str) -> str:
    stopwords = {
        "the", "a", "an", "and", "or", "but", "if",
        "is", "are", "was", "were", "be", "been",
        "being", "to", "of", "in", "on", "for",
        "with", "as", "by", "at", "from", "that",
        "this", "these", "those", "it", "its",
        "into", "about", "than", "then", "so",
        "such", "their", "there", "have", "has",
        "had", "do", "does", "did", "can", "could",
        "will", "would", "should", "may", "might",
        "we", "you", "they", "he", "she", "them",
        "his", "her", "our", "your", "i", "me",
        "my", "mine", "us",
    }

    query_tokens = re.findall(r"\w+", query_text.lower())
    query_tokens = [
        token for token in query_tokens
        if token not in stopwords and len(token) > 2
    ]

    phrases = set()

    for size in range(5, 1, -1):
        for i in range(len(query_tokens) - size + 1):
            phrase = " ".join(query_tokens[i:i + size])
            if phrase and phrase in source_text.lower():
                phrases.add(phrase)

    highlighted = source_text

    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda m: f"<mark>{m.group(0)}</mark>",
            highlighted,
        )

    return highlighted


def extract_best_evidence(source_text: str, query_text: str) -> str:
    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", source_text)
        if p.strip()
    ]

    if not paragraphs:
        return source_text

    return max(
        paragraphs,
        key=lambda p: SequenceMatcher(None, p.lower(), query_text.lower()).ratio(),
    )


def aggregate_document_score(scores: list[float]) -> float:
    max_score = max(scores)
    avg_score = sum(scores) / len(scores)
    match_bonus = min(len(scores) / 3.0, 1.0)
    final_score = (0.7 * max_score) + (0.2 * avg_score) + (0.1 * match_bonus)
    return round(final_score, 4)

def token_overlap_ratio(a: str, b: str) -> float:
    a_tokens = set(re.findall(r"\w+", a.lower()))
    b_tokens = set(re.findall(r"\w+", b.lower()))

    if not a_tokens or not b_tokens:
        return 0.0

    overlap = a_tokens & b_tokens
    return len(overlap) / min(len(a_tokens), len(b_tokens))

def check_plagiarism(
    text: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> PlagiarismCheckResponse:
    input_chunks = chunk_text(text)

    if not input_chunks:
        return PlagiarismCheckResponse(
            message="No valid input text found",
            input_text_length=0,
            total_chunks=0,
            overall_similarity=0.0,
            threshold_used=threshold,
            matches=[],
            plagiarism_detected=False,
        )

    reference_records, reference_embeddings, faiss_index = load_index()

    if len(reference_records) == 0 or reference_embeddings.size == 0:
        return PlagiarismCheckResponse(
            message="No indexed reference documents found",
            input_text_length=len(text),
            total_chunks=len(input_chunks),
            overall_similarity=0.0,
            threshold_used=threshold,
            matches=[],
            plagiarism_detected=False,
        )

    input_embeddings = encode_texts(input_chunks)
    input_embeddings = np.ascontiguousarray(input_embeddings.astype("float32"))
    faiss.normalize_L2(input_embeddings)

    scores, indices = faiss_index.search(input_embeddings, TOP_K)

    grouped_matches: dict[str, list[RawMatch]] = defaultdict(list)

    for input_index, input_chunk in enumerate(input_chunks):
        for rank, ref_index in enumerate(indices[input_index]):
            if ref_index < 0:
                continue

            score = float(scores[input_index][rank])
            if score < threshold:
                continue

            matched_record: ChunkRecord = reference_records[ref_index]
            overlap = token_overlap_ratio(input_chunk, matched_record.text)

            if score < 0.80 and overlap < 0.20:
                continue
            evidence = extract_best_evidence(matched_record.text, input_chunk)
            highlighted = highlight_overlap(evidence, input_chunk)

            grouped_matches[matched_record.filename].append(
                RawMatch(
                    document_id=matched_record.document_id,
                    filename=matched_record.filename,
                    similarity_score=round(score, 4),
                    matched_text=evidence,
                    highlighted_match=highlighted,
                    input_chunk=input_chunk,
                )
            )

    final_matches: list[MatchResult] = []

    for filename, matches in grouped_matches.items():
        raw_scores = [m.similarity_score for m in matches]
        best_match = max(matches, key=lambda x: x.similarity_score)
        avg_score = round(sum(raw_scores) / len(raw_scores), 4)
        final_score = aggregate_document_score(raw_scores)

        final_matches.append(
            MatchResult(
                document_id=filename,
                similarity_score=best_match.similarity_score,
                matched_text=best_match.matched_text,
                highlighted_match=best_match.highlighted_match,
                input_chunk=best_match.input_chunk,
                match_count=len(matches),
                average_score=avg_score,
                final_score=final_score,
            )
        )

    final_matches = sorted(
        final_matches,
        key=lambda x: (x.final_score, x.similarity_score, x.match_count),
        reverse=True,
    )

    overall_similarity = (
        round(sum(match.final_score for match in final_matches) / len(final_matches), 2)
        if final_matches
        else 0.0
    )

    return PlagiarismCheckResponse(
        message="Plagiarism check completed",
        input_text_length=len(text),
        total_chunks=len(input_chunks),
        overall_similarity=overall_similarity,
        threshold_used=threshold,
        matches=final_matches[:FINAL_TOP_N],
        plagiarism_detected=len(final_matches) > 0,
    )