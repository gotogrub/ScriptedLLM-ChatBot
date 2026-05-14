# ScriptedLLM ChatBot

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/RAG-LangChain-1f6f43)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-0f172a)](https://www.langchain.com/langgraph)
[![ScriptedLLM](https://img.shields.io/badge/Guardrails-ScriptedLLM-111827)](https://github.com/gotogrub/ScriptedLLM)
[![License](https://img.shields.io/badge/License-CC0%201.0-0f766e)](LICENSE)

ScriptedLLM ChatBot is a small RAG assistant for internal office requests. It uses LangChain document objects for local retrieval, LangGraph for workflow orchestration with a safe fallback, SQLite for memory, and [ScriptedLLM](https://github.com/gotogrub/ScriptedLLM) style output validation.

The local LLM path was tested with Ollama and `qwen2.5:7b`. The UI can also run in scripted fallback mode, change model settings, inspect RAG chunks, and review the outgoing payload.

## Stack

Python 3.11, LangChain Core, LangGraph.

SQLite, standard library HTTP server, HTML/CSS/JavaScript.

Ollama, ScriptedLLM guardrails, local `.reg` catalog rules.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python -m chatbot
```

Open `http://127.0.0.1:8081`.

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
