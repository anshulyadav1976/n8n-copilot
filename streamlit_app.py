import os
from typing import Any, Optional
import json
import logging

import streamlit as st

from n8n_client import N8nClient
from agent import build_agent
from logging_config import setup_logging
from json_templates import (
    http_request_node,
    set_node,
    if_node,
    function_node,
    simple_flow_http_set_if,
)


APP_TITLE = "n8n Copilot (MVP)"


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state["messages"] = []  # list[dict(role, content)]
    if "n8n_base_url" not in st.session_state:
        st.session_state["n8n_base_url"] = ""
    if "n8n_api_key" not in st.session_state:
        st.session_state["n8n_api_key"] = ""
    if "n8n_client" not in st.session_state:
        st.session_state["n8n_client"] = None
    if "selected_workflow_id" not in st.session_state:
        st.session_state["selected_workflow_id"] = None


def sidebar_config() -> None:
    with st.sidebar:
        st.header("Configuration")
        st.caption("Your keys are not persisted beyond the session.")

        st.session_state["n8n_base_url"] = st.text_input(
            "n8n Base URL",
            value=st.session_state.get("n8n_base_url", ""),
            placeholder="https://your-n8n.example.com",
        )
        st.session_state["n8n_api_key"] = st.text_input(
            "n8n API Key",
            value=st.session_state.get("n8n_api_key", ""),
            type="password",
            placeholder="Paste X-N8N-API-KEY",
        )

        if st.button("Validate & Connect", use_container_width=True):
            try:
                client = N8nClient(
                    base_url=st.session_state["n8n_base_url"].strip(),
                    api_key=st.session_state["n8n_api_key"].strip(),
                )
                client.test_connection()
                st.session_state["n8n_client"] = client
                st.success("Connected to n8n instance ✔")
            except Exception as exc:  # noqa: BLE001
                st.session_state["n8n_client"] = None
                st.error(f"Connection failed: {exc}")


def render_workflows_panel() -> None:
    client: Optional[N8nClient] = st.session_state.get("n8n_client")
    if not client:
        st.info("Connect to your n8n instance to load workflows.")
        return

    try:
        workflows = client.list_workflows()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to load workflows: {exc}")
        return

    workflow_options = []
    id_to_workflow: dict[str, Any] = {}
    # Workflows can be returned as a dict with 'data' depending on n8n version.
    payload = workflows.get("data", workflows) if isinstance(workflows, dict) else workflows
    for wf in payload:
        wf_id = str(wf.get("id"))
        name = wf.get("name", f"Workflow {wf_id}")
        workflow_options.append(f"{name} (ID: {wf_id})")
        id_to_workflow[f"{name} (ID: {wf_id})"] = wf

    selection = st.selectbox("Select workflow", workflow_options)
    if selection:
        st.session_state["selected_workflow_id"] = str(id_to_workflow[selection].get("id"))

        try:
            wf = client.get_workflow(st.session_state["selected_workflow_id"])
            st.subheader("Workflow JSON")
            st.json(wf)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load workflow: {exc}")


def render_executions_panel() -> None:
    client: Optional[N8nClient] = st.session_state.get("n8n_client")
    if not client:
        return

    wf_id = st.session_state.get("selected_workflow_id")
    st.subheader("Executions")
    col1, col2, col3 = st.columns(3)
    with col1:
        status = st.selectbox("Status", ["", "success", "error", "waiting", "running"])
    with col2:
        limit = st.number_input("Limit", min_value=1, max_value=200, value=20, step=1)
    with col3:
        offset = st.number_input("Offset", min_value=0, value=0, step=1)

    if st.button("Load Executions"):
        try:
            executions = client.list_executions(
                workflow_id=wf_id, status=status or None, limit=int(limit), offset=int(offset)
            )
            st.json(executions)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load executions: {exc}")


def render_chat() -> None:
    st.header(APP_TITLE)
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"]) 

    prompt = st.chat_input("Ask the copilot about your workflows...")
    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            try:
                client: Optional[N8nClient] = st.session_state.get("n8n_client")
                if not client:
                    st.warning("Connect to n8n first in the sidebar.")
                    reply = "Please connect to your n8n instance first."
                else:
                    agent = build_agent(client)
                    result = agent.invoke({"input": prompt})
                    reply = result.get("output", "(No response)")
                st.markdown(reply)
                st.session_state["messages"].append({"role": "assistant", "content": reply})
            except Exception as exc:  # noqa: BLE001
                st.error(f"Agent error: {exc}")


def generate_node_json(node_type: str, name: str) -> dict:
    node_type_lower = (node_type or "").strip().lower()
    name = name.strip() or "New Node"

    if node_type_lower in {"http", "http request", "http_request", "httprequest"}:
        return http_request_node(name=name)
    if node_type_lower in {"set", "set node"}:
        return set_node(name=name)
    if node_type_lower in {"if", "condition", "conditional"}:
        return if_node(name=name)
    # Generic template
    return function_node(name=name)


def render_suggestions_panel() -> None:
    st.subheader("Suggestions — JSON Snippets")
    st.caption("Generate copyable node JSON to paste into the n8n editor (read-only MVP)")

    node_type = st.text_input("Node type (e.g., HTTP Request, Set, IF)")
    node_name = st.text_input("Node name", value="Suggested Node")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Generate Node JSON"):
            snippet = generate_node_json(node_type=node_type, name=node_name)
            st.json(snippet)
            st.download_button(
                label="Download JSON",
                data=(json.dumps(snippet, indent=2)).encode("utf-8"),
                file_name=f"{(node_name or 'node').replace(' ', '_').lower()}.json",
                mime="application/json",
            )
    with col_b:
        if st.button("Generate Mini Flow (HTTP→Set→IF)"):
            flow = simple_flow_http_set_if()
            st.json(flow)
            st.download_button(
                label="Download Flow JSON",
                data=(json.dumps(flow, indent=2)).encode("utf-8"),
                file_name="mini_flow_http_set_if.json",
                mime="application/json",
            )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    setup_logging()
    init_session_state()
    sidebar_config()

    left, right = st.columns([0.6, 0.4])
    with left:
        render_chat()
    with right:
        render_workflows_panel()
        render_executions_panel()
        render_suggestions_panel()


if __name__ == "__main__":
    main()


