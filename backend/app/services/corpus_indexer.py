
from __future__ import annotations

import gc
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import faiss
import numpy as np

from app.services.chunking import clean_text, chunk_text
from app.services.embedder import encode_texts


# ============================================================
# 1. DIRECTORY CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "indexes"

FAISS_INDEX_FILE = INDEX_DIR / "faiss.index"
CHUNKS_FILE = PROCESSED_DIR / "chunks.json"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"

# Process only 16 chunks per model call.
ENCODING_BATCH_SIZE = 16


# ============================================================
# 2. CHUNK RECORD
# ============================================================

@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    filename: str
    source_path: str
    chunk_index: int
    text: str


# ============================================================
# 3. CREATE REQUIRED DIRECTORIES
# ============================================================

def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 4. LOAD REFERENCE TXT DOCUMENTS
# ============================================================

def load_txt_documents() -> list[tuple[str, Path, str]]:

    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"Raw data directory not found: {RAW_DIR}"
        )

    documents = []

    for file_path in sorted(RAW_DIR.rglob("*.txt")):

        text = clean_text(
            file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        )

        if text:
            documents.append(
                (file_path.stem, file_path, text)
            )

    return documents


# ============================================================
# 5. BUILD CHUNK RECORDS
# ============================================================

def build_chunk_records() -> list[ChunkRecord]:

    records = []

    for document_id, file_path, text in load_txt_documents():

        chunks = chunk_text(
            text,
            chunk_size=300,
            overlap=50
        )

        for chunk_index, chunk in enumerate(chunks):

            records.append(
                ChunkRecord(
                    chunk_id=f"{document_id}::chunk_{chunk_index}",
                    document_id=document_id,
                    filename=file_path.name,
                    source_path=str(file_path),
                    chunk_index=chunk_index,
                    text=chunk
                )
            )

    return records


# ============================================================
# 6. ENCODE RECORDS IN BATCHES
# ============================================================

def encode_records_in_batches(
    records: list[ChunkRecord],
    batch_size: int = ENCODING_BATCH_SIZE,
) -> np.ndarray:

    """
    Encode chunks in small batches to reduce peak RAM usage.
    """

    embedding_batches = []

    total = len(records)

    for start in range(0, total, batch_size):

        end = min(start + batch_size, total)

        batch_records = records[start:end]

        batch_texts = [
            record.text for record in batch_records
        ]

        batch_embeddings = encode_texts(batch_texts)

        batch_embeddings = np.asarray(
            batch_embeddings,
            dtype=np.float32
        )

        batch_embeddings = np.ascontiguousarray(
            batch_embeddings
        )

        if batch_embeddings.ndim != 2:
            raise ValueError(
                "Embedding model returned an invalid array."
            )

        if batch_embeddings.shape[0] != len(batch_records):
            raise ValueError(
                "Embedding count does not match batch size."
            )

        # Normalize each batch before adding it to FAISS.
        faiss.normalize_L2(batch_embeddings)

        embedding_batches.append(batch_embeddings)

        print(
            f"Encoded {end}/{total} chunks"
        )

        del batch_texts
        del batch_records
        del batch_embeddings

        gc.collect()

    if not embedding_batches:
        raise ValueError("No embeddings were generated.")

    embeddings = np.concatenate(
        embedding_batches,
        axis=0
    )

    del embedding_batches
    gc.collect()

    return np.ascontiguousarray(
        embeddings,
        dtype=np.float32
    )


# ============================================================
# 7. SAVE INDEX FILES
# ============================================================

def _write_index_artifacts(
    records: list[ChunkRecord],
    embeddings: np.ndarray,
    index: faiss.Index | None = None,
) -> None:

    ensure_dirs()

    embeddings = np.ascontiguousarray(
        embeddings,
        dtype=np.float32
    )

    if index is None:

        index = faiss.IndexFlatIP(
            embeddings.shape[1]
        )

        if len(embeddings):
            index.add(embeddings)

    chunks_tmp = CHUNKS_FILE.with_name(
        "chunks.json.tmp"
    )

    embeddings_tmp = EMBEDDINGS_FILE.with_name(
        "embeddings.npy.tmp"
    )

    index_tmp = FAISS_INDEX_FILE.with_name(
        "faiss.index.tmp"
    )

    with chunks_tmp.open("w", encoding="utf-8") as f:

        json.dump(
            [asdict(record) for record in records],
            f,
            ensure_ascii=False,
            indent=2
        )

    with embeddings_tmp.open("wb") as f:
        np.save(f, embeddings)

    faiss.write_index(
        index,
        str(index_tmp)
    )

    # Replace the previous saved artifacts.
    chunks_tmp.replace(CHUNKS_FILE)
    embeddings_tmp.replace(EMBEDDINGS_FILE)
    index_tmp.replace(FAISS_INDEX_FILE)


# ============================================================
# 8. BUILD COMPLETE REFERENCE INDEX
# ============================================================

def build_index() -> dict[str, int]:

    ensure_dirs()

    records = build_chunk_records()

    if not records:
        raise ValueError(
            "No valid TXT documents found in data/raw"
        )

    print(
        f"Starting batch encoding for {len(records)} chunks..."
    )

    embeddings = encode_records_in_batches(
        records,
        batch_size=ENCODING_BATCH_SIZE
    )

    print("Building FAISS index...")

    index = faiss.IndexFlatIP(
        embeddings.shape[1]
    )

    # Add embeddings in batches.
    for start in range(
        0,
        len(embeddings),
        ENCODING_BATCH_SIZE
    ):

        end = min(
            start + ENCODING_BATCH_SIZE,
            len(embeddings)
        )

        index.add(embeddings[start:end])

    _write_index_artifacts(
        records,
        embeddings,
        index
    )

    result = {
        "documents_indexed": len({
            record.document_id for record in records
        }),
        "chunks_indexed": len(records),
    }

    print("FAISS index successfully built.")

    return result


# ============================================================
# 9. LOAD EXISTING INDEX
# ============================================================

def load_index() -> tuple[
    list[ChunkRecord],
    np.ndarray,
    faiss.Index
]:

    """
    Load the already-created index.

    IMPORTANT:
    This function does not compare the saved index against
    the current raw TXT corpus.

    This prevents unnecessary re-encoding of the complete
    reference corpus every time the backend starts.
    """

    needs_build = not (
        CHUNKS_FILE.exists()
        and EMBEDDINGS_FILE.exists()
        and FAISS_INDEX_FILE.exists()
    )

    raw_records = None
    saved_index = None

    if not needs_build:

        try:

            # Load saved chunk metadata.
            with CHUNKS_FILE.open(
                "r",
                encoding="utf-8"
            ) as f:

                raw_records = json.load(f)

            # Load saved embeddings without memory mapping.
            saved_embeddings = np.load(
                EMBEDDINGS_FILE
            )

            # Load saved FAISS index.
            saved_index = faiss.read_index(
                str(FAISS_INDEX_FILE)
            )

            # Check whether all saved artifacts match.
            needs_build = (
                len(raw_records) != saved_index.ntotal
                or len(raw_records) != saved_embeddings.shape[0]
                or saved_embeddings.ndim != 2
                or saved_embeddings.shape[1] != saved_index.d
            )

            del saved_embeddings
            gc.collect()

            if not needs_build:
                print(
                    f"Existing index found: "
                    f"{len(raw_records)} chunks."
                )

                print(
                    "Loading saved FAISS index. "
                    "No full-corpus encoding required."
                )

        except Exception as exc:

            print(
                f"Existing index validation failed: {exc}"
            )

            needs_build = True

    # Rebuild only if saved artifacts are missing or invalid.
    if needs_build:

        print(
            "Index missing or invalid; "
            "rebuilding reference corpus..."
        )

        build_index()

        with CHUNKS_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:

            raw_records = json.load(f)

        saved_index = faiss.read_index(
            str(FAISS_INDEX_FILE)
        )

    records = [
        ChunkRecord(**item)
        for item in raw_records
    ]

    # Load embeddings into normal memory.
    embeddings = np.load(
        EMBEDDINGS_FILE
    ).astype(
        np.float32,
        copy=False
    )

    return records, embeddings, saved_index


# ============================================================
# 10. ADD NEW DOCUMENTS WITHOUT RE-ENCODING OLD DOCUMENTS
# ============================================================

def add_documents_to_index(
    file_paths: list[Path]
) -> dict[str, int]:

    # Load existing chunk records.
    with CHUNKS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        records = [
            ChunkRecord(**item)
            for item in json.load(f)
        ]

    # Load existing embeddings.
    embeddings = np.load(
        EMBEDDINGS_FILE
    ).astype(
        np.float32,
        copy=False
    )

    # Load existing FAISS index.
    index = faiss.read_index(
        str(FAISS_INDEX_FILE)
    )

    if not isinstance(index, faiss.IndexFlatIP):
        raise ValueError(
            "Unexpected FAISS index type. "
            "Rebuild the index before adding documents."
        )

    # Validate existing index before adding new documents.
    if (
        len(records) != index.ntotal
        or len(records) != embeddings.shape[0]
    ):
        raise ValueError(
            "Existing index files are inconsistent. "
            "Do not add documents until the index is repaired."
        )

    existing_document_ids = {
        record.document_id for record in records
    }

    new_records = []

    for file_path in file_paths:

        if file_path.stem in existing_document_ids:
            raise ValueError(
                f"Document already indexed: {file_path.name}"
            )

        text = clean_text(
            file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )
        )

        chunks = chunk_text(
            text,
            chunk_size=300,
            overlap=50
        )

        for chunk_index, chunk in enumerate(chunks):

            new_records.append(
                ChunkRecord(
                    chunk_id=f"{file_path.stem}::chunk_{chunk_index}",
                    document_id=file_path.stem,
                    filename=file_path.name,
                    source_path=str(file_path),
                    chunk_index=chunk_index,
                    text=chunk
                )
            )

    if not new_records:
        raise ValueError(
            "No indexable text was found in uploaded documents."
        )

    print(
        f"Encoding {len(new_records)} new chunks..."
    )

    # Encode ONLY the newly uploaded documents.
    new_embeddings = encode_records_in_batches(
        new_records,
        batch_size=ENCODING_BATCH_SIZE
    )

    # Add new vectors to the existing FAISS index.
    for start in range(
        0,
        len(new_embeddings),
        ENCODING_BATCH_SIZE
    ):

        end = min(
            start + ENCODING_BATCH_SIZE,
            len(new_embeddings)
        )

        index.add(
            new_embeddings[start:end]
        )

    # Combine old and new embedding arrays.
    combined_embeddings = np.concatenate(
        [
            embeddings,
            new_embeddings
        ],
        axis=0
    )

    combined_records = records + new_records

    # Save the updated index.
    _write_index_artifacts(
        combined_records,
        combined_embeddings,
        index
    )

    result = {
        "documents_indexed": len({
            record.document_id
            for record in combined_records
        }),
        "chunks_indexed": len(combined_records),
        "new_documents": len(file_paths),
        "new_chunks": len(new_records),
    }

    print(
        f"Added {len(file_paths)} new documents "
        f"with {len(new_records)} new chunks."
    )

    return result
