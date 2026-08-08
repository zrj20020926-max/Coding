"""Redis fixed-window limits for authentication entry points."""

from collections.abc import Iterable
from hashlib import sha256
from ipaddress import ip_address, ip_network
from time import time

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _trusted_proxy(peer: str) -> bool:
    try:
        peer_address = ip_address(peer)
    except ValueError:
        return False
    for value in settings.trusted_proxy_cidrs.split(","):
        candidate = value.strip()
        if candidate and peer_address in ip_network(candidate, strict=False):
            return True
    return False


def get_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for and _trusted_proxy(peer):
        candidate = forwarded_for.split(",", maxsplit=1)[0].strip()
        try:
            return str(ip_address(candidate))
        except ValueError:
            pass
    try:
        return str(ip_address(peer))
    except ValueError:
        return peer


async def enforce_auth_rate_limit(
    cache: Redis,
    *,
    action: str,
    client_ip: str,
    account_identities: Iterable[str],
    ip_limit: int,
    account_limit: int,
) -> None:
    window = settings.auth_rate_limit_window_seconds
    now = int(time())
    bucket = now // window
    dimensions = [(f"ip:{_digest(client_ip)}", ip_limit)]
    dimensions.extend(
        (f"account:{_digest(identity.strip().lower())}", account_limit)
        for identity in account_identities
    )

    async with cache.pipeline(transaction=True) as pipeline:
        for dimension, _ in dimensions:
            key = f"auth:rate:{action}:{dimension}:{bucket}"
            pipeline.incr(key)
            pipeline.expire(key, window * 2)
        results = await pipeline.execute()

    counts = [int(results[index]) for index in range(0, len(results), 2)]
    if any(count > limit for count, (_, limit) in zip(counts, dimensions)):
        retry_after = max(1, window - (now % window))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试"},
            headers={"Retry-After": str(retry_after)},
        )
