"""
Simple n8n REST API client (read-only for MVP).

Endpoints used (per https://docs.n8n.io/api/):
- GET /rest/workflows
- GET /rest/workflows/{id}
- GET /rest/executions
- GET /rest/executions/{id}

Authentication: X-N8N-API-KEY header
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def test_connection(self) -> bool:
        """Validate API connectivity by making a lightweight request.

        Uses GET /rest/workflows with a small page to avoid heavy payloads.
        Returns True on HTTP 200; raises on errors.
        """
        url = self._url("/rest/workflows")
        response = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
        response.raise_for_status()
        return True

    def list_workflows(self) -> Any:
        url = self._url("/rest/workflows")
        response = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def get_workflow(self, workflow_id: str | int) -> Any:
        url = self._url(f"/rest/workflows/{workflow_id}")
        response = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
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
        url = self._url("/rest/executions")
        params: Dict[str, Any] = {}
        if workflow_id is not None:
            params["workflowId"] = workflow_id
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        response = requests.get(
            url, headers=self._headers(), params=params, timeout=self.timeout_seconds
        )
        response.raise_for_status()
        return response.json()

    def get_execution(self, execution_id: str | int) -> Any:
        url = self._url(f"/rest/executions/{execution_id}")
        response = requests.get(url, headers=self._headers(), timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()


__all__ = ["N8nClient"]


