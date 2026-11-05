# Plagiarism Detection

A FastAPI-based semantic plagiarism checker using multilingual Sentence-BERT embeddings and FAISS.

## Features

- Text and PDF/TXT submission for plagiarism checks.
- Semantic chunk matching with `paraphrase-multilingual-MiniLM-L12-v2`.
- FAISS cosine-similarity search.
- Separate administrator login for reference corpus management.
- Admin can upload 1–5 PDF/TXT reference files per batch and repeat uploads.
- Uploaded originals are retained under `backend/data/reference_originals/`.
- Extracted text is added to the reference corpus and indexed for subsequent checks.
- Duplicate uploaded files are rejected by SHA-256 hash.

## Setup

Use Python 3.10+ (a compatible PyTorch/Sentence-Transformers build is required).

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Edit `backend/.env` and set:
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` (use a long, unique password)
- `ADMIN_TOKEN_SECRET` (at least 32 random characters)

Generate a token secret, for example:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the generated value into `ADMIN_TOKEN_SECRET`.

## Build the complete reference index

The earlier project indexed only the first 20 TXT files. The updated indexer processes all TXT files under `backend/data/raw`.

From the `backend` directory:

```powershell
python ..\scripts\build_index.py
```

The first run downloads the Sentence-Transformers model if it is not cached and may take time depending on CPU/GPU and corpus size.

## Run the backend

From the `backend` directory:

```powershell
python -m uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

## Run the frontend

Open the `frontend` folder with VS Code Live Server, or serve it on port 5500. The frontend expects the API at `http://127.0.0.1:8000`.

- Plagiarism checker: `frontend/index.html`
- Administrator login: `frontend/admin-login.html`
- Reference dashboard: `frontend/admin.html` (requires login)

## Administrator workflow

1. Open `admin-login.html`.
2. Sign in using credentials from `backend/.env`.
3. Select 1–5 PDF/TXT documents.
4. Select **Upload and index**.
5. After successful indexing, the documents become available to subsequent plagiarism checks.
6. Repeat the upload for additional batches.

Each file is limited to 5 MB. PDFs must contain selectable text; scanned/image-only PDFs need OCR, which is not included.

## Important operational notes

- Administrator tokens expire after 8 hours and are held in browser session storage.
- Use HTTPS, a strong unique password, a secret key, and a production-grade server before exposing this application outside a trusted local network.
- Keep `backend/.env` and uploaded reference documents private.
- FAISS uses exact inner-product search over normalized vectors (equivalent to cosine similarity).
- Rebuilding the index from the full corpus happens automatically if the saved index does not match the TXT corpus. You can also rebuild manually with the script above.
- The current matching thresholds are heuristic and must be validated on labelled plagiarism/non-plagiarism examples before making accuracy claims.
=======
# The-Plagiarism-Detector

