
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# Keep inference batches small to reduce RAM consumption.
MODEL_BATCH_SIZE = 16


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    model = SentenceTransformer(MODEL_NAME)

    # CPU inference avoids unexpected GPU allocation.
    model.to("cpu")

    return model


def encode_texts(texts: list[str]) -> np.ndarray:

    if not texts:
        return np.empty((0, 384), dtype=np.float32)

    model = get_model()

    embeddings = model.encode(
        texts,
        batch_size=MODEL_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    return np.asarray(
        embeddings,
        dtype=np.float32
    )
