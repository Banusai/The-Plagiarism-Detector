from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    document_id: str = Field(
        ...,
        description="Reference document identifier",
    )
    similarity_score: float = Field(
        ...,
        description="Best chunk similarity score",
    )
    matched_text: str = Field(
        ...,
        description="Most similar chunk from reference document",
    )
    highlighted_match: str = Field(
        ...,
        description="Matched text with highlighted overlap",
    )
    input_chunk: str = Field(
        ...,
        description="Input chunk that matched",
    )
    match_count: int = Field(
        1,
        description="Number of chunk-level matches found for this document",
    )
    average_score: float = Field(
        0.0,
        description="Average similarity score across matched chunks",
    )
    final_score: float = Field(
        0.0,
        description="Final aggregated document ranking score",
    )


class PlagiarismCheckResponse(BaseModel):
    message: str = Field(
        ...,
        description="Status message for plagiarism check",
    )
    input_text_length: int = Field(
        ...,
        description="Length of submitted text in characters",
    )
    total_chunks: int = Field(
        ...,
        description="Number of chunks created from input text",
    )
    overall_similarity: float = Field(
        ...,
        description="Overall aggregated similarity score",
    )
    threshold_used: float = Field(
        ...,
        description="Similarity threshold used for filtering matches",
    )
    matches: list[MatchResult] = Field(
        default_factory=list,
        description="Top ranked plagiarism matches",
    )
    plagiarism_detected: bool = Field(
        ...,
        description="Whether plagiarism was detected above threshold",
    )