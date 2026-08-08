FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --retries 5 --index-url "$PIP_INDEX_URL" .

USER app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
