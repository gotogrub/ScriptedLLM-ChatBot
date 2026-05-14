var messages = document.getElementById("messages");
var form = document.getElementById("chatForm");
var input = document.getElementById("messageInput");
var userId = document.getElementById("userId");
var quickReplies = document.getElementById("quickReplies");
var draftView = document.getElementById("draftView");
var sourcesView = document.getElementById("sourcesView");
var ticketView = document.getElementById("ticketView");
var resetButton = document.getElementById("resetButton");
var refreshModelsButton = document.getElementById("refreshModelsButton");
var openLogsButton = document.getElementById("openLogsButton");
var closeLogsButton = document.getElementById("closeLogsButton");
var logsDialog = document.getElementById("logsDialog");
var traceLogView = document.getElementById("traceLogView");
var chunksLogView = document.getElementById("chunksLogView");
var payloadLogView = document.getElementById("payloadLogView");
var logTabs = document.querySelectorAll(".log-tabs button");
var providerSelect = document.getElementById("providerSelect");
var modelSelect = document.getElementById("modelSelect");
var baseUrlInput = document.getElementById("baseUrlInput");
var temperatureInput = document.getElementById("temperatureInput");
var topPInput = document.getElementById("topPInput");
var topKInput = document.getElementById("topKInput");
var ragTopKInput = document.getElementById("ragTopKInput");
var numCtxInput = document.getElementById("numCtxInput");
var timeoutInput = document.getElementById("timeoutInput");
var lastDebug = null;

function appendMessage(role, text, timestamp) {
  var wrap = document.createElement("div");
  wrap.className = "message " + role;
  var bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  var meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = (role === "user" ? "Вы" : "Бот") + " · " + formatTime(timestamp);
  wrap.appendChild(bubble);
  wrap.appendChild(meta);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

function formatTime(value) {
  var date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) {
    date = new Date();
  }
  return date.toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit", second: "2-digit"});
}

function renderQuickReplies(items) {
  quickReplies.innerHTML = "";
  if (!items || !items.length) {
    return;
  }
  items.forEach(function(item) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = item;
    button.addEventListener("click", function() {
      input.value = item;
      form.requestSubmit();
    });
    quickReplies.appendChild(button);
  });
}

function renderSources(items) {
  sourcesView.innerHTML = "";
  if (!items || !items.length) {
    sourcesView.textContent = "RAG-контекст появится после запроса";
    return;
  }
  items.forEach(function(item) {
    var block = document.createElement("div");
    block.className = "source-item";
    var title = document.createElement("div");
    title.className = "source-title";
    title.textContent = item.title + ", score " + item.score;
    var text = document.createElement("div");
    text.textContent = item.text;
    block.appendChild(title);
    block.appendChild(text);
    sourcesView.appendChild(block);
  });
}

function currentOptions() {
  return {
    provider: providerSelect.value,
    model: modelSelect.value,
    base_url: baseUrlInput.value,
    temperature: Number(temperatureInput.value),
    top_p: Number(topPInput.value),
    top_k: Number(topKInput.value),
    rag_top_k: Number(ragTopKInput.value),
    num_ctx: Number(numCtxInput.value),
    timeout: Number(timeoutInput.value)
  };
}

function renderState(result) {
  if (result.draft && Object.keys(result.draft).length) {
    draftView.textContent = JSON.stringify(result.draft, null, 2);
  } else {
    draftView.textContent = "Нет активного черновика";
  }
  if (result.ticket) {
    ticketView.textContent = JSON.stringify(result.ticket, null, 2);
  }
  renderSources(result.citations || []);
  renderQuickReplies(result.quick_replies || []);
  if (result.debug && Object.keys(result.debug).length) {
    renderLogs(result.debug);
  }
  if (result.validated === false && result.violations && result.violations.length) {
    appendMessage("assistant", "Нарушения валидации: " + result.violations.join("; "));
  }
}

function renderLogs(debug) {
  lastDebug = debug;
  renderTraceLog(debug);
  renderChunksLog(debug);
  renderPayloadLog(debug);
}

function renderTraceLog(debug) {
  clearNode(traceLogView);
  if (!debug) {
    appendLogBlock(traceLogView, "Trace", [{label: "status", value: "empty"}]);
    return;
  }
  appendLogBlock(traceLogView, "Request", [
    {label: "created_at", value: debug.created_at},
    {label: "provider", value: debug.provider},
    {label: "model", value: debug.model},
    {label: "base_url", value: debug.base_url},
    {label: "message", value: debug.message !== undefined ? debug.message : "not available"}
  ]);
  renderHistoryBlock(debug.history || []);
  (debug.llm || []).forEach(function(item, index) {
    var rows = [
      {label: "step", value: String(index + 1)},
      {label: "purpose", value: item.purpose},
      {label: "status", value: item.status},
      {label: "fallback_used", value: item.fallback_used},
      {label: "endpoint", value: item.endpoint || "not called"},
      {label: "reason", value: item.reason},
      {label: "message", value: item.message},
      {label: "previous_request_type", value: item.previous_request_type},
      {label: "previous_draft", value: item.previous_draft},
      {label: "classification", value: formatClassification(item.classification)},
      {label: "guarded_from", value: formatClassification(item.guarded_classification)},
      {label: "guarded_reason", value: item.guarded_reason},
      {label: "response", value: item.response},
      {label: "error", value: item.error},
      {label: "eval_count", value: item.eval_count},
      {label: "prompt_eval_count", value: item.prompt_eval_count}
    ];
    appendLogBlock(traceLogView, "LLM Decision", rows);
  });
  if (debug.rag) {
    appendLogBlock(traceLogView, "RAG", [
      {label: "top_k", value: debug.rag.top_k},
      {label: "request_type", value: debug.rag.request_type},
      {label: "missing_fields", value: (debug.rag.missing_fields || []).join(", ") || "none"},
      {label: "chunks", value: debug.rag.chunks ? debug.rag.chunks.length : 0}
    ]);
  }
  if (debug.validation) {
    appendLogBlock(traceLogView, "Validation", [
      {label: "valid", value: debug.validation.valid},
      {label: "violations", value: (debug.validation.violations || []).join(", ") || "none"}
    ]);
  }
  if (debug.models) {
    appendLogBlock(traceLogView, "Models", [
      {label: "status", value: debug.models.status},
      {label: "endpoint", value: debug.models.endpoint},
      {label: "models", value: (debug.models.models || []).join(", ")},
      {label: "error", value: debug.models.error}
    ]);
  }
}

function renderHistoryBlock(history) {
  var block = createLogBlock("Dialog History");
  if (!history.length) {
    block.appendChild(logRow("messages", "empty"));
    traceLogView.appendChild(block);
    return;
  }
  history.forEach(function(item) {
    var message = document.createElement("div");
    message.className = "log-message";
    var meta = document.createElement("div");
    meta.className = "log-message-role";
    meta.textContent = (item.role || "unknown") + " · " + formatTime(item.created_at);
    var content = document.createElement("div");
    content.textContent = item.content || "";
    message.appendChild(meta);
    message.appendChild(content);
    block.appendChild(message);
  });
  traceLogView.appendChild(block);
}

function renderChunksLog(debug) {
  clearNode(chunksLogView);
  var chunks = debug && debug.rag ? debug.rag.chunks || [] : [];
  if (!chunks.length) {
    appendLogBlock(chunksLogView, "Chunks", [{label: "status", value: "empty"}]);
    return;
  }
  chunks.forEach(function(chunk) {
    appendLogBlock(chunksLogView, "Chunk " + chunk.rank, [
      {label: "id", value: chunk.id},
      {label: "title", value: chunk.title},
      {label: "category", value: chunk.category},
      {label: "reference", value: chunk.reference},
      {label: "score", value: chunk.score},
      {label: "characters", value: chunk.characters},
      {label: "text", value: chunk.text}
    ]);
  });
}

function renderPayloadLog(debug) {
  clearNode(payloadLogView);
  if (!debug || !debug.llm || !debug.llm.length) {
    appendLogBlock(payloadLogView, "Payload", [{label: "status", value: "LLM payload is not available yet"}]);
    return;
  }
  debug.llm.forEach(function(trace, index) {
    var block = createLogBlock("Payload " + (index + 1) + ": " + (trace.purpose || "unknown"));
    block.appendChild(logRow("status", trace.status));
    block.appendChild(logRow("endpoint", trace.endpoint || "not called"));
    block.appendChild(logRow("model", trace.model));
    block.appendChild(logRow("classification", formatClassification(trace.classification)));
    block.appendChild(logJson("request", trace.payload || {status: "not available"}));
    block.appendChild(logJson("response", {
      response: trace.response,
      fallback: trace.fallback,
      error: trace.error,
      eval_count: trace.eval_count,
      prompt_eval_count: trace.prompt_eval_count
    }));
    payloadLogView.appendChild(block);
  });
}

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function createLogBlock(title) {
  var block = document.createElement("section");
  block.className = "log-block";
  var heading = document.createElement("h3");
  heading.textContent = title;
  block.appendChild(heading);
  return block;
}

function appendLogBlock(parent, title, rows) {
  var block = createLogBlock(title);
  rows.forEach(function(row) {
    if (row.value !== undefined && row.value !== null && row.value !== "") {
      block.appendChild(logRow(row.label, row.value));
    }
  });
  parent.appendChild(block);
}

function logRow(label, value) {
  var row = document.createElement("div");
  row.className = "log-row";
  var key = document.createElement("div");
  key.className = "log-label";
  key.textContent = label;
  var val = document.createElement("div");
  val.className = "log-value";
  val.textContent = formatLogValue(value);
  row.appendChild(key);
  row.appendChild(val);
  return row;
}

function logJson(label, value) {
  var wrap = document.createElement("div");
  wrap.className = "log-json-wrap";
  var key = document.createElement("div");
  key.className = "log-label";
  key.textContent = label;
  var pre = document.createElement("pre");
  pre.className = "log-json";
  pre.textContent = JSON.stringify(value, null, 2);
  wrap.appendChild(key);
  wrap.appendChild(pre);
  return wrap;
}

function formatClassification(value) {
  if (!value) {
    return "";
  }
  return [value.action, value.confidence, value.reason].filter(function(item) {
    return item !== undefined && item !== null && item !== "";
  }).join(" · ");
}

function formatLogValue(value) {
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function setActiveLogTab(tabName) {
  logTabs.forEach(function(button) {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  traceLogView.classList.toggle("active", tabName === "trace");
  chunksLogView.classList.toggle("active", tabName === "chunks");
  payloadLogView.classList.toggle("active", tabName === "payload");
}

function openLogs() {
  if (!lastDebug) {
    renderLogs({status: "empty", message: "Логи появятся после запроса"});
  }
  if (logsDialog.showModal) {
    logsDialog.showModal();
  } else {
    logsDialog.setAttribute("open", "open");
  }
}

function closeLogs() {
  if (logsDialog.close) {
    logsDialog.close();
  } else {
    logsDialog.removeAttribute("open");
  }
}

function sendMessage(text) {
  appendMessage("user", text);
  return fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({user_id: userId.value || "demo", message: text, options: currentOptions()})
  })
    .then(function(response) {
      return response.json();
    })
    .then(function(result) {
      appendMessage("assistant", result.answer);
      renderState(result);
    })
    .catch(function() {
      appendMessage("assistant", "Сервер недоступен. Проверьте, что приложение запущено.");
    });
}

function loadSettings() {
  return fetch("/api/settings")
    .then(function(response) {
      return response.json();
    })
    .then(function(settings) {
      providerSelect.value = settings.provider || "ollama";
      baseUrlInput.value = settings.base_url || "http://localhost:11434";
      temperatureInput.value = settings.temperature;
      topPInput.value = settings.top_p;
      topKInput.value = settings.top_k;
      ragTopKInput.value = settings.rag_top_k;
      numCtxInput.value = settings.num_ctx;
      timeoutInput.value = settings.timeout;
      if (settings.model) {
        modelSelect.dataset.configuredModel = settings.model;
        ensureModelOption(settings.model);
        modelSelect.value = settings.model;
      }
      return refreshModels();
    });
}

function ensureModelOption(model) {
  var exists = false;
  Array.prototype.forEach.call(modelSelect.options, function(option) {
    if (option.value === model) {
      exists = true;
    }
  });
  if (!exists) {
    var option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    if (model === "") {
      option.disabled = true;
    }
    modelSelect.appendChild(option);
  }
}

function refreshModels() {
  var url = "/api/models?base_url=" + encodeURIComponent(baseUrlInput.value);
  var configuredModel = modelSelect.dataset.configuredModel || modelSelect.value;
  modelSelect.disabled = true;
  modelSelect.innerHTML = "";
  ensureModelOption("");
  modelSelect.options[0].textContent = "Loading models";
  modelSelect.value = "";
  return fetch(url)
    .then(function(response) {
      return response.json();
    })
    .then(function(result) {
      if (result.status === "ok" && result.models.length) {
        modelSelect.innerHTML = "";
        result.models.forEach(function(model) {
          var option = document.createElement("option");
          option.value = model;
          option.textContent = model;
          modelSelect.appendChild(option);
        });
        if (result.models.indexOf(configuredModel) >= 0) {
          modelSelect.value = configuredModel;
        } else {
          modelSelect.value = result.models[0];
        }
        modelSelect.dataset.configuredModel = modelSelect.value;
        modelSelect.disabled = false;
      } else {
        modelSelect.innerHTML = "";
        ensureModelOption(configuredModel || "");
        modelSelect.value = configuredModel || "";
        modelSelect.dataset.configuredModel = configuredModel;
        modelSelect.disabled = false;
      }
      renderLogs({models: result});
    })
    .catch(function() {
      modelSelect.innerHTML = "";
      ensureModelOption(configuredModel || "");
      modelSelect.value = configuredModel || "";
      modelSelect.dataset.configuredModel = configuredModel;
      modelSelect.disabled = false;
      renderLogs({models: {status: "error", error: "Не удалось получить список моделей Ollama."}});
    });
}

form.addEventListener("submit", function(event) {
  event.preventDefault();
  var text = input.value.trim();
  if (!text) {
    return;
  }
  input.value = "";
  sendMessage(text);
});

resetButton.addEventListener("click", function() {
  fetch("/api/reset", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({user_id: userId.value || "demo"})
  }).then(function() {
    draftView.textContent = "Нет активного черновика";
    ticketView.textContent = "Заявка еще не создана";
    sourcesView.textContent = "RAG-контекст появится после запроса";
    renderLogs({status: "reset"});
    quickReplies.innerHTML = "";
    appendMessage("assistant", "Диалог сброшен.");
  });
});

refreshModelsButton.addEventListener("click", function() {
  refreshModels();
});

modelSelect.addEventListener("change", function() {
  modelSelect.dataset.configuredModel = modelSelect.value;
});

openLogsButton.addEventListener("click", function() {
  openLogs();
});

closeLogsButton.addEventListener("click", function() {
  closeLogs();
});

logsDialog.addEventListener("click", function(event) {
  if (event.target === logsDialog) {
    closeLogs();
  }
});

logTabs.forEach(function(button) {
  button.addEventListener("click", function() {
    setActiveLogTab(button.dataset.tab);
  });
});

appendMessage("assistant", "Здравствуйте. Опишите заявку в АХО или выберите сценарий.");
renderQuickReplies(["Заказ канцтоваров", "SIM-карта", "Командировка", "Парковка", "Такси", "Непорядок"]);
loadSettings();
