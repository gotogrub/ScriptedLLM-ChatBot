import json
import urllib.error
import urllib.parse
import urllib.request

from aho_bot.schemas import LLMResult


class LLMClient:
    def __init__(self, settings):
        self.settings = settings

    def runtime_options(self, incoming=None):
        incoming = incoming or {}
        return {
            "provider": str(incoming.get("provider") or self.settings.llm_provider).strip().lower(),
            "model": str(incoming.get("model") or self.settings.llm_model).strip(),
            "base_url": str(incoming.get("base_url") or self.settings.llm_base_url).strip(),
            "temperature": self.float_option(incoming, "temperature", self.settings.llm_temperature),
            "top_p": self.float_option(incoming, "top_p", self.settings.llm_top_p),
            "top_k": self.int_option(incoming, "top_k", self.settings.llm_top_k),
            "num_ctx": self.int_option(incoming, "num_ctx", self.settings.llm_num_ctx),
            "timeout": self.int_option(incoming, "timeout", self.settings.llm_timeout),
            "rag_top_k": self.int_option(incoming, "rag_top_k", self.settings.rag_top_k),
        }

    def float_option(self, incoming, key, default):
        try:
            return float(incoming.get(key, default))
        except (TypeError, ValueError):
            return default

    def int_option(self, incoming, key, default):
        try:
            return int(incoming.get(key, default))
        except (TypeError, ValueError):
            return default

    def compose(self, user_message, facts, fallback, incoming=None, purpose="chat"):
        options = self.runtime_options(incoming)
        provider = options["provider"]
        if provider == "ollama":
            return self.call_ollama(user_message, facts, fallback, options, purpose)
        if provider in ["openai", "openai-compatible"]:
            return self.call_openai_compatible(user_message, facts, fallback, options, purpose)
        trace = self.trace_template(provider, options, purpose)
        trace["status"] = "scripted"
        trace["fallback_used"] = True
        trace["fallback"] = fallback
        return LLMResult(fallback, trace)

    def call_ollama(self, user_message, facts, fallback, options, purpose):
        url = options["base_url"].rstrip("/") + "/api/chat"
        system = self.system_prompt(facts, fallback)
        payload = {
            "model": options["model"],
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "options": {
                "temperature": options["temperature"],
                "top_p": options["top_p"],
                "top_k": options["top_k"],
                "num_ctx": options["num_ctx"],
            },
        }
        trace = self.trace_template("ollama", options, purpose)
        trace["endpoint"] = url
        trace["payload"] = self.safe_payload(payload)
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=options["timeout"]) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            trace["status"] = "fallback"
            trace["error"] = str(error)
            trace["fallback_used"] = True
            trace["fallback"] = fallback
            return LLMResult(fallback, trace)
        message = body.get("message", {})
        text = (message.get("content") or "").strip()
        if not text:
            trace["status"] = "fallback"
            trace["error"] = "empty model response"
            trace["fallback_used"] = True
            trace["fallback"] = fallback
            return LLMResult(fallback, trace)
        trace["status"] = "generated"
        trace["fallback_used"] = False
        trace["response"] = text
        trace["eval_count"] = body.get("eval_count")
        trace["prompt_eval_count"] = body.get("prompt_eval_count")
        return LLMResult(text, trace)

    def call_openai_compatible(self, user_message, facts, fallback, options, purpose):
        if not self.settings.llm_api_key:
            trace = self.trace_template("openai-compatible", options, purpose)
            trace["status"] = "fallback"
            trace["error"] = "missing api key"
            trace["fallback_used"] = True
            trace["fallback"] = fallback
            return LLMResult(fallback, trace)
        url = options["base_url"].rstrip("/") + "/chat/completions"
        system = self.system_prompt(facts, fallback)
        payload = {
            "model": options["model"],
            "temperature": options["temperature"],
            "top_p": options["top_p"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        }
        trace = self.trace_template("openai-compatible", options, purpose)
        trace["endpoint"] = url
        trace["payload"] = self.safe_payload(payload)
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.llm_api_key}",
        }
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=options["timeout"]) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            trace["status"] = "fallback"
            trace["error"] = str(error)
            trace["fallback_used"] = True
            trace["fallback"] = fallback
            return LLMResult(fallback, trace)
        choices = body.get("choices") or []
        text = ""
        if choices:
            text = (choices[0].get("message", {}).get("content") or "").strip()
        if not text:
            trace["status"] = "fallback"
            trace["error"] = "empty model response"
            trace["fallback_used"] = True
            trace["fallback"] = fallback
            return LLMResult(fallback, trace)
        trace["status"] = "generated"
        trace["fallback_used"] = False
        trace["response"] = text
        return LLMResult(text, trace)

    def list_ollama_models(self, base_url=None):
        url = (base_url or self.settings.llm_base_url).rstrip("/") + "/api/tags"
        request = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            return {"status": "error", "models": [], "error": str(error), "endpoint": url}
        models = []
        for item in body.get("models", []):
            name = item.get("name")
            if name:
                models.append(name)
        return {"status": "ok", "models": models, "endpoint": url}

    def system_prompt(self, facts, fallback):
        return (
            "Ты АХО-бот. Переформулируй безопасный черновик в один короткий русский ответ. "
            "Не меняй смысл, поля, варианты выбора, числа и товары. "
            "Не добавляй новых фактов, сроков, цен или обещаний. "
            f"Факты:\n{facts}\n\n"
            f"Черновик:\n{fallback}"
        )

    def trace_template(self, provider, options, purpose):
        return {
            "purpose": purpose,
            "provider": provider,
            "model": options.get("model"),
            "base_url": options.get("base_url"),
            "options": {
                "temperature": options.get("temperature"),
                "top_p": options.get("top_p"),
                "top_k": options.get("top_k"),
                "num_ctx": options.get("num_ctx"),
                "timeout": options.get("timeout"),
            },
        }

    def safe_payload(self, payload):
        safe = json.loads(json.dumps(payload, ensure_ascii=False))
        for message in safe.get("messages", []):
            content = message.get("content", "")
            if len(content) > 3500:
                message["content"] = content[:3500] + "\n..."
        return safe
