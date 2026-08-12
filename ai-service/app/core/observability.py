import json
import logging
from datetime import UTC, datetime

from prometheus_client import Counter, Gauge, Histogram

ANALYSES = Counter(
    "codearena_ai_analyses_total",
    "AI analysis outcomes",
    ["outcome"],
)
PROVIDER_RETRIES = Counter("codearena_ai_provider_retries_total", "Provider retry attempts")
PROVIDER_LATENCY = Histogram(
    "codearena_ai_provider_latency_seconds",
    "Model provider call latency",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60),
)
TOKENS = Counter("codearena_ai_tokens_total", "Model tokens", ["kind"])
COST_MICROUSD = Counter("codearena_ai_cost_microusd_total", "Estimated provider cost")
QUEUE_PENDING = Gauge("codearena_ai_queue_pending", "Pending Redis Stream entries")
QUEUE_LAG = Gauge("codearena_ai_queue_lag", "Undelivered Redis Stream entries")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if not message:
            message = "log event"
        message = message[:1000]
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        for key in ("analysis_id", "event", "status", "retry_count", "latency_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
