"""
Simple n8n REST API client (read-only for MVP).

Endpoints used (per https://do  cs.n8n.io/api/):
- GET /rest/workflows
- GET /rest/workflows/{id}
- GET /rest/executions
- GET /rest/executions/{id}

Authentication: X-N8N-API-KEY header
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import logging
import time
import requests


class N8nClient:
    """Thin client for the n8n REST API.

    This client only implements read-only operations required by the MVP.
    """

    def __init__(self, base_url: str, api_key: str, timeout_seconds: int = 30) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not api_key:
            raise ValueError("api_key is required")

        self.base_url: str = base_url.rstrip("/")
        self.api_key: str = api_key
        self.timeout_seconds: int = timeout_seconds
        # Auto-detect whether the instance expects Public API ("/api/v1") or legacy REST ("/rest")
        self._api_prefix: Optional[str] = None  # set on first successful request

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _ensure_prefix(self) -> None:
        """Detect which API prefix the n8n instance supports.

        Tries the Public API first ("/api/v1"), then legacy REST ("/rest").
        Caches the first prefix that returns HTTP 200.
        """
        if self._api_prefix:
            return

        candidates = ["/api/v1", "/rest"]
        last_exc: Optional[Exception] = None
        for prefix in candidates:
            try:
                url = self._url(f"{prefix}/workflows")
                resp = self._get_with_retry(url, params={"limit": 1})
                if resp.status_code == 200:
                    self._api_prefix = prefix
                    return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue

        # If none worked, raise the last error (or a generic one)
        if last_exc:
            raise last_exc
        raise RuntimeError("Failed to detect n8n API prefix. Check base URL and API key.")

    def test_connection(self) -> bool:
        """Validate API connectivity by making a lightweight request.

        Uses GET /rest/workflows with a small page to avoid heavy payloads.
        Returns True on HTTP 200; raises on errors.
        """
        self._ensure_prefix()
        url = self._url(f"{self._api_prefix}/workflows")
        response = self._get_with_retry(url)
        response.raise_for_status()
        return True

    def list_workflows(self, *, fetch_all: bool = True, limit: int = 100) -> Any:
        """List workflows, optionally fetching all pages (Public API).

        - For Public API ("/api/v1"), pagination uses `limit` and `cursor` with `nextCursor` in response.
        - For legacy REST ("/rest"), pagination typically is not required; returns all.
        Returns either the raw JSON from the API or a dict with `data` when aggregating pages.
        """
        self._ensure_prefix()
        url = self._url(f"{self._api_prefix}/workflows")

        # If not public API or fetch_all is False, just do a single call
        if (self._api_prefix != "/api/v1") or not fetch_all:
            response = self._get_with_retry(url)
            response.raise_for_status()
            return response.json()

        # Public API with pagination
        all_items = []
        cursor: Optional[str] = None
        while True:
            params: Dict[str, Any] = {"limit": limit}
            if cursor:
                params["cursor"] = cursor
            response = self._get_with_retry(url, params=params)
            response.raise_for_status()
            payload = response.json()
            page_items = payload.get("data", payload) if isinstance(payload, dict) else payload
            if isinstance(page_items, list):
                all_items.extend(page_items)
            else:
                # Unexpected shape; return raw payload
                return payload
            cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
            if not cursor:
                break

        return {"data": all_items}

    def get_workflow(self, workflow_id: str | int) -> Any:
        self._ensure_prefix()
        url = self._url(f"{self._api_prefix}/workflows/{workflow_id}")
        response = self._get_with_retry(url)
        response.raise_for_status()
        return response.json()

    def list_executions(
        self,
        *,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = 20,
        offset: Optional[int] = 0,
    ) -> Any:
        self._ensure_prefix()
        url = self._url(f"{self._api_prefix}/executions")
        params: Dict[str, Any] = {}
        if workflow_id is not None:
            params["workflowId"] = workflow_id
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        response = self._get_with_retry(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_execution(self, execution_id: str | int) -> Any:
        self._ensure_prefix()
        url = self._url(f"{self._api_prefix}/executions/{execution_id}")
        response = self._get_with_retry(url)
        response.raise_for_status()
        return response.json()

    # --- Internal helpers with simple retry/backoff and logging ---
    def _get_with_retry(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        logger = logging.getLogger("n8n_client")
        attempts = 0
        delay_seconds = 0.5
        while True:
            attempts += 1
            try:
                response = requests.get(
                    url, headers=self._headers(), params=params, timeout=self.timeout_seconds
                )
                if response.status_code in (429, 502, 503, 504):
                    # handle rate limit or transient upstream issues
                    if attempts < 4:
                        logger.warning(
                            "Transient %s from n8n. Retrying in %.1fs (attempt %d)",
                            response.status_code,
                            delay_seconds,
                            attempts,
                        )
                        time.sleep(delay_seconds)
                        delay_seconds *= 2
                        continue
                return response
            except requests.RequestException as exc:  # covers timeouts, connection errors
                if attempts < 4:
                    logger.warning(
                        "Request error '%s'. Retrying in %.1fs (attempt %d)",
                        exc,
                        delay_seconds,
                        attempts,
                    )
                    time.sleep(delay_seconds)
                    delay_seconds *= 2
                    continue
                raise


__all__ = ["N8nClient"]


