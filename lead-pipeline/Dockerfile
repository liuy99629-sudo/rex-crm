# Local runner and tests for the AWS lead pipeline. On AWS the same code runs as a Lambda (template.yaml).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY leads ./leads
COPY samples ./samples

FROM base AS test
COPY requirements-dev.txt pytest.ini ./
RUN pip install -r requirements-dev.txt
COPY tests ./tests
CMD ["pytest", "-q"]

FROM base AS local
RUN useradd --uid 10001 --no-create-home rex
USER rex
CMD ["python", "-m", "leads.local"]
