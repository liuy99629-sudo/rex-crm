# Rex AI service (FastAPI + LangGraph + sentence-transformers on CPU).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf TRANSFORMERS_OFFLINE=0
WORKDIR /app

# CPU-only PyTorch keeps the image ~1 GB smaller than the default CUDA build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model into the image: no download at start, works offline.
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"
ENV HF_HUB_OFFLINE=1 EMBEDDING_MODEL=${EMBEDDING_MODEL}

COPY app ./app

# Tests: docker compose --profile test run --rm ai-test
FROM base AS test
COPY requirements-dev.txt pytest.ini ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests
CMD ["pytest", "-q"]

FROM base AS app
RUN useradd --uid 10001 --no-create-home rex
USER rex
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=60s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ai/health')"
CMD ["uvicorn", "app.main:production_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
