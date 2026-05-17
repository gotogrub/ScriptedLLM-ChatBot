# ScriptedLLM ChatBot

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/RAG-LangChain-1f6f43)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-0f172a)](https://www.langchain.com/langgraph)
[![ScriptedLLM](https://img.shields.io/badge/Guardrails-ScriptedLLM-111827)](https://github.com/gotogrub/ScriptedLLM)
[![License](https://img.shields.io/badge/License-CC0%201.0-0f766e)](LICENSE)

Английская версия: [README.md](README.md)

ScriptedLLM ChatBot это локальный RAG-ассистент для внутренних заявок в АХО. Основной демо-сценарий собирает заявки на канцтовары и продукты для кухни, ведет структурированный черновик, уточняет недостающие поля и создает JSON-заявку только после подтверждения пользователя.

Локальный LLM-сценарий тестировался с Ollama и `qwen2.5:7b`. Если модель недоступна, приложение может отвечать через детерминированные резервные ответы.

## Архитектура

Браузерный интерфейс из `static/` отправляет запросы в HTTP-сервер на стандартной библиотеке из `src/chatbot/server.py`. Сервер отдает страницу и API для чата, сброса диалога, истории заявок, настроек, проверки состояния и получения списка моделей Ollama.

`ChatbotService` работает как слой оркестрации. На каждом сообщении он сохраняет историю в SQLite, загружает активную сессию, классифицирует ход диалога, извлекает сущности, достает релевантные знания, просит LLM сформулировать ответ, валидирует результат и сохраняет сообщение ассистента.

Слой знаний читает JSON-файлы и `data/catalog.reg`, превращает их в документы LangChain и индексирует легким лексическим поисковиком. LangGraph используется для перехода между сбором данных и состоянием готовности к подтверждению, а при недоступности LangGraph есть локальный резервный путь.

## Стек

- Python 3.11+, HTTP-сервер на стандартной библиотеке, SQLite.
- LangChain Core, LangGraph, валидация ответов в стиле ScriptedLLM.
- Ollama или чат-API, совместимый с OpenAI, HTML/CSS/JavaScript, Docker.

## Запуск

Локальный запуск:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
python -m chatbot
```

После запуска откройте `http://127.0.0.1:8081`.

Для ответов через LLM должна быть запущена Ollama с моделью `qwen2.5:7b`, либо можно выбрать другую установленную модель в интерфейсе. Если нужен внешний пакет ScriptedLLM вместо локального совместимого валидатора, установите проект командой `pip install -e ".[scriptedllm]"`.

Основные переменные конфигурации: `CHATBOT_LLM_PROVIDER`, `CHATBOT_LLM_MODEL`, `CHATBOT_LLM_BASE_URL`, `CHATBOT_PORT`, `CHATBOT_DATABASE_PATH`.

## Docker

Если Ollama установлена локально на Linux, контейнер нужно запускать в host network, чтобы приложение видело `127.0.0.1:11434`.

```bash
docker build -t scriptedllm-chatbot .
docker run -d --name scriptedllm-chatbot --network host -e CHATBOT_HOST=127.0.0.1 -e CHATBOT_PORT=8081 -e CHATBOT_LLM_PROVIDER=ollama -e CHATBOT_LLM_MODEL=qwen2.5:7b -e CHATBOT_LLM_BASE_URL=http://127.0.0.1:11434 scriptedllm-chatbot
```

Если контейнер уже создан, используйте `docker start scriptedllm-chatbot`. Остановить его можно командой `docker stop scriptedllm-chatbot`.

## Тестирование

Тесты используют scripted-провайдер и временные SQLite-базы, поэтому Ollama для прогона не нужна.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Принятые решения

- Гибридное понимание запроса: устойчивые сущности извлекаются детерминированно через `.reg`-каталог, а LLM классифицирует более мягкие намерения и формулирует ответы.
- RAG до генерации: в модель передаются найденные факты и безопасный резервный ответ, поэтому модель не должна придумывать цены, регламенты или статус создания заявки.
- Guardrails и наблюдаемость: [ScriptedLLM](https://github.com/gotogrub/ScriptedLLM) используется при установке пакета, рядом есть локальный совместимый валидатор и debug trace с промптами, чанками, историей и результатами валидации.

## Ограничения

- Поиск локальный и лексический, без embedding-based semantic search.
- База знаний и каталог демо-размера, расширяются через JSON и `.reg`-данные.
- Это прототип без production-аутентификации, интеграции с внешней ticket-системой и полноценной multilingual-поддержки.
