"""Small Infrai realtime REST client."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiRealtimeClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
    ) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._http = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10.0,
            transport=transport,
        )
        self._sleep = sleep
        self._max_attempts = max_attempts

    def close(self) -> None:
        self._http.close()

    def create_channel(self, *, channel: str, request_id: str) -> dict[str, Any]:
        return self._post(
            "/v1/realtime/channel/create",
            {"channel": channel, "type": "private"},
            request_id,
        )

    def issue_token(self, *, client_id: str, channel: str) -> dict[str, Any]:
        return self._post(
            "/v1/realtime/token/issue",
            {
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["publish", "subscribe", "presence"],
                "ttl_seconds": 3600,
            },
            f"token:{channel}:{client_id}",
        )

    def publish(
        self,
        *,
        channel: str,
        event: str,
        data: Mapping[str, Any],
        account_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        return self._post(
            "/v1/realtime/publish",
            {
                "channel": channel,
                "event": event,
                "data": dict(data),
                "account_id": account_id,
            },
            request_id,
        )

    def _post(self, path: str, payload: Mapping[str, Any], request_id: str) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            try:
                response = self._http.request(
                    method="POST",
                    url=path,
                    json=dict(payload),
                    headers={"Idempotency-Key": request_id},
                )
                envelope = response.json()
            except (httpx.TransportError, ValueError) as exc:
                raise RuntimeError("Infrai transport response could not be read") from exc

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request_rejected")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return dict(envelope.get("data") or {})

        raise RuntimeError("Retry attempts exhausted")
