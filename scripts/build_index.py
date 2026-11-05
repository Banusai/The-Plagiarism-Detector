import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).resolve().parents[1] / "backend")
)

from app.services.corpus_indexer import build_index


if __name__ == "__main__":
    stats = build_index()

    print(
        f"Indexed "
        f"{stats['documents_indexed']} documents / "
        f"{stats['chunks_indexed']} chunks"
    )