# n8n Copilot (MVP)

Streamlit-based AI copilot for n8n. MVP is read-only: browse workflows, executions, and get suggested JSON snippets to copy into n8n.

## Quickstart

1) Python 3.11+ recommended
2) Create a virtualenv and install requirements

```bash
pip install -r requirements.txt
```

3) Run the app

```bash
streamlit run streamlit_app.py
```

4) In the sidebar, enter:
- n8n Base URL
- n8n API Key (header `X-N8N-API-KEY`)

Then click “Validate & Connect”.

## LLM via OpenRouter
- Default provider: OpenRouter (OpenAI-compatible API)
- Set `OPENROUTER_API_KEY` and (optionally) `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- To enable built-in web search, use ":online" models (e.g., `openrouter/auto:online`)
- Docs: https://openrouter.ai/docs/features/web-search

## Local Storage
- MVP uses local SQLite where needed (later we’ll migrate to Postgres + pgvector)
- A `data/` folder is provided for local files

## References
- n8n Public API: https://docs.n8n.io/api/
- Auth: https://docs.n8n.io/api/authentication/
- Streamlit Chat: https://docs.streamlit.io/library/api-reference/chat
- OpenRouter API: https://openrouter.ai/docs

## Notes
- Keys are not persisted beyond the Streamlit session in MVP
- Writing/executing workflows is intentionally disabled in MVP
