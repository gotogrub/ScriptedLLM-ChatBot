# ScriptedLLM ChatBot

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/RAG-LangChain-1f6f43)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-0f172a)](https://www.langchain.com/langgraph)
[![ScriptedLLM](https://img.shields.io/badge/Guardrails-ScriptedLLM-111827)](https://github.com/gotogrub/ScriptedLLM)
[![License](https://img.shields.io/badge/License-CC0%201.0-0f766e)](LICENSE)

Russian version: [README_RU.md](README_RU.md)

ScriptedLLM ChatBot is a local RAG assistant for internal office requests. The main demo path collects procurement requests for office supplies and kitchen products, keeps a typed draft, asks for missing fields, and creates a JSON ticket only after the user confirms it.

The local LLM flow was tested with Ollama and `qwen2.5:7b`. The app can also fall back to scripted answers when an LLM provider is unavailable.

## Architecture

The browser UI in `static/` calls the standard-library HTTP server in `src/chatbot/server.py`. The API exposes chat, reset, ticket history, runtime settings, health checks, and Ollama model discovery.

`ChatbotService` coordinates each turn: it writes the user message to SQLite, loads the session, classifies the turn, extracts entities, retrieves knowledge, asks the LLM for safe wording, validates the answer, and stores the assistant response.

The knowledge layer loads JSON facts plus `data/catalog.reg`, builds LangChain document objects, and indexes them with a compact lexical retriever. LangGraph controls the transition between data collection and confirmation, with a local fallback if LangGraph is not available.

## Stack

- Python 3.11+, standard-library HTTP server, SQLite.
- LangChain Core, LangGraph, ScriptedLLM-compatible output validation.
- Ollama or OpenAI-compatible chat API, HTML/CSS/JavaScript, Docker.

## Run

Local run:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python -m chatbot
```

Open `http://127.0.0.1:8081`.

For LLM-backed answers, keep Ollama running and pull `qwen2.5:7b`, or select another installed model in the UI. Use `pip install -e ".[scriptedllm]"` when you want the external ScriptedLLM package instead of the local compatible validator.

Useful configuration variables are `CHATBOT_LLM_PROVIDER`, `CHATBOT_LLM_MODEL`, `CHATBOT_LLM_BASE_URL`, `CHATBOT_PORT`, and `CHATBOT_DATABASE_PATH`.

## Docker

For local Ollama on Linux, run the container on the host network so it can reach `127.0.0.1:11434`.

```bash
docker build -t scriptedllm-chatbot .
docker run -d --name scriptedllm-chatbot --network host -e CHATBOT_HOST=127.0.0.1 -e CHATBOT_PORT=8081 -e CHATBOT_LLM_PROVIDER=ollama -e CHATBOT_LLM_MODEL=qwen2.5:7b -e CHATBOT_LLM_BASE_URL=http://127.0.0.1:11434 scriptedllm-chatbot
```

If the container already exists, use `docker start scriptedllm-chatbot`. Stop it with `docker stop scriptedllm-chatbot`.

## Test

The test suite uses the scripted provider and temporary SQLite databases, so Ollama is not required.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Decisions

- Hybrid understanding: deterministic `.reg` catalog rules extract stable entities, while the LLM classifies softer turn intent and phrases answers.
- RAG before generation: retrieved facts and a safe fallback answer are passed to the LLM, and the model is not allowed to invent prices, policies, or completion status.
- Guardrails and observability: [ScriptedLLM](https://github.com/gotogrub/ScriptedLLM) validation is used when installed, with a local compatible validator and debug traces for prompts, chunks, history, and validation results.

## Limitations

- Retrieval is lexical and local, not embedding-based semantic search.
- The knowledge base and catalog are demo-sized and must be extended through JSON and `.reg` data.
- This is a prototype without production authentication, external ticket-system integration, or full multilingual coverage.
