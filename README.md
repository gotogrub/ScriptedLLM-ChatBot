# ScriptedLLM ChatBot with RAG

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57)](https://www.sqlite.org/)
[![ScriptedLLM](https://img.shields.io/badge/Guardrails-ScriptedLLM-111827)](https://github.com/gotogrub/ScriptedLLM)
[![License](https://img.shields.io/badge/License-CC0%201.0-0f766e)](LICENSE)

ScriptedLLM ChatBot is a compact RAG chatbot for internal requests. It combines deterministic workflow orchestration, a small knowledge base, conversational memory, and response validation by the [ScriptedLLM](https://github.com/gotogrub/ScriptedLLM) constrained-dialog model.

## Stack

| Layer | Technology |
| --- | --- |
| Runtime | Python 3.11+ |
| Web | Standard library HTTP server, HTML, CSS, JavaScript |
| Memory | SQLite |

## Capabilities

- RAG over local company policy and employee data.
- Scripted workflows that collect missing request fields.
- JSON request creation with validation and status history.

## LLM Backends

The default backend is Ollama with `qwen2.5:7b`. The UI can switch models, tune sampling, change RAG top-k, and inspect the exact request trace.

```bash
export AHO_LLM_PROVIDER=ollama
export AHO_LLM_MODEL=llama3.2
python -m aho_bot
```

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python -m aho_bot
```

Open `http://127.0.0.1:8080`.

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
