FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system --gid 10001 judge \
    && adduser --system --uid 10001 --ingroup judge judge

COPY pyproject.toml ./
COPY app ./app
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --retries 5 --index-url "$PIP_INDEX_URL" .

FROM base AS test

RUN pip install --no-cache-dir --retries 5 --index-url "$PIP_INDEX_URL" ".[dev]"
COPY tests ./tests
USER judge
CMD ["python", "-m", "pytest", "-p", "no:cacheprovider", "-m", "unit"]

FROM base AS runtime

USER judge
CMD ["python", "-m", "app.main"]
