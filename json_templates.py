from __future__ import annotations

from typing import Any, Dict, List


def http_request_node(name: str = "HTTP Request", url: str = "https://api.example.com/", method: str = "GET") -> Dict[str, Any]:
    return {
        "parameters": {
            "authentication": "none",
            "requestMethod": method,
            "url": url,
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4,
        "name": name,
        "position": [0, 0],
    }


def set_node(name: str = "Set", key: str = "key", value: str = "value") -> Dict[str, Any]:
    return {
        "parameters": {
            "keepOnlySet": False,
            "values": {
                "string": [
                    {"name": key, "value": value},
                ]
            },
        },
        "type": "n8n-nodes-base.set",
        "typeVersion": 2,
        "name": name,
        "position": [0, 0],
    }


def if_node(name: str = "IF", left: str = "={{$json.key}}", op: str = "equals", right: str = "value") -> Dict[str, Any]:
    return {
        "parameters": {
            "conditions": {
                "string": [
                    {"value1": left, "operation": op, "value2": right},
                ]
            }
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "name": name,
        "position": [0, 0],
    }


def function_node(name: str = "Function", code: str | None = None) -> Dict[str, Any]:
    return {
        "parameters": {
            "functionCode": code
            or "return items.map(item => { item.json.added = true; return item; });",
        },
        "type": "n8n-nodes-base.function",
        "typeVersion": 2,
        "name": name,
        "position": [0, 0],
    }


def simple_flow_http_set_if() -> Dict[str, Any]:
    """Return a minimal workflow fragment: HTTP Request -> Set -> IF with connections.

    This is a snippet users can merge into an existing workflow JSON.
    """
    http = http_request_node(name="HTTP Request")
    http["position"] = [0, 0]
    setn = set_node(name="Set", key="key", value="value")
    setn["position"] = [260, 0]
    iff = if_node(name="IF", left="={{$json.key}}", op="equals", right="value")
    iff["position"] = [520, 0]

    connections = {
        "HTTP Request": {
            "main": [[{"node": "Set", "type": "main", "index": 0}]]
        },
        "Set": {
            "main": [[{"node": "IF", "type": "main", "index": 0}]]
        },
    }

    return {
        "nodes": [http, setn, iff],
        "connections": connections,
    }


__all__ = [
    "http_request_node",
    "set_node",
    "if_node",
    "function_node",
    "simple_flow_http_set_if",
]


