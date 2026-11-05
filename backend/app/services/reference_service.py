from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, UploadFile, status

from app.core.config import (
    DATA_DIR,
    MAX_FILE_SIZE_BYTES,
    MAX_FILES_PER_UPLOAD,
    RAW_DIR,
    REFERENCE_METADATA_FILE,
    REFERENCE_ORIGINALS_DIR,
)
from app.services.corpus_indexer import add_documents_to_index, load_index
from app.services.file_parser import parse_file_bytes
from app.services.chunking import chunk_text

_reference_lock = Lock()


def _read_metadata() -> list[dict]:
    if not REFERENCE_METADATA_FILE.exists():
        return []
    try:
        data = json.loads(REFERENCE_METADATA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reference document metadata is unreadable. Contact the administrator.",
        )


def list_reference_documents() -> list[dict]:
    metadata = _read_metadata()
    return sorted(metadata, key=lambda item: item.get("created_at", ""), reverse=True)


def upload_reference_documents(files: list[UploadFile]) -> dict:
    if not 1 <= len(files) <= MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload between 1 and 5 reference documents per batch.",
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)

    with _reference_lock:
        metadata = _read_metadata()
        known_hashes = {item.get("sha256") for item in metadata}

        prepared = []
        batch_hashes = set()
        for upload in files:
            if not upload.filename:
                raise HTTPException(status_code=400, detail="Every uploaded file must have a filename.")
            filename = Path(upload.filename.replace("\\\\", "/")).name
            suffix = Path(filename).suffix.lower()
            if suffix not in {".pdf", ".txt"}:
                raise HTTPException(status_code=415, detail=f"{filename}: only PDF and TXT files are supported.")

            content = upload.file.read(MAX_FILE_SIZE_BYTES + 1)
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail=f"{filename}: maximum file size is 5 MB.")
            digest = hashlib.sha256(content).hexdigest()
            if digest in known_hashes or digest in batch_hashes:
                raise HTTPException(status_code=409, detail=f"{filename}: this document has already been added.")
            extracted = parse_file_bytes(filename, upload.content_type, content)
            batch_hashes.add(digest)
            prepared.append((filename, suffix, content, digest, extracted))

        # Ensure the pre-existing corpus is fully indexed before adding new files.
        # This also repairs older indexes built with the former 20-document limit.
        load_index()

        new_metadata = []
        new_text_paths: list[Path] = []
        created_paths: list[Path] = []
        try:
            for filename, suffix, content, digest, extracted in prepared:
                document_id = uuid.uuid4().hex
                safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "reference"
                original_name = f"{document_id}_{safe_name}"
                original_path = REFERENCE_ORIGINALS_DIR / original_name
                text_path = RAW_DIR / f"reference_{document_id}.txt"

                original_path.write_bytes(content)
                text_path.write_text(extracted, encoding="utf-8")
                created_paths.extend([original_path, text_path])
                new_text_paths.append(text_path)

                new_metadata.append({
                    "id": document_id,
                    "filename": filename,
                    "stored_filename": original_name,
                    "format": suffix.lstrip(".").upper(),
                    "size_bytes": len(content),
                    "sha256": digest,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "indexing",
                    "chunks_added": 0,
                })

            index_stats = add_documents_to_index(new_text_paths)

            for item in new_metadata:
                item["status"] = "indexed"
                matching_path = next(
                    path for path in new_text_paths
                    if path.stem == f"reference_{item['id']}"
                )
                item["chunks_added"] = len(
                    chunk_text(matching_path.read_text(encoding="utf-8"), chunk_size=300, overlap=50)
                )
            metadata.extend(new_metadata)
            temp_metadata = REFERENCE_METADATA_FILE.with_suffix(".json.tmp")
            temp_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            temp_metadata.replace(REFERENCE_METADATA_FILE)

            return {
                "message": f"Successfully added {len(new_metadata)} reference document(s) to the corpus.",
                "documents": new_metadata,
                "index": index_stats,
            }
        except Exception as exc:
            for path in created_paths:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Reference upload/indexing failed: {exc}",
            ) from exc
