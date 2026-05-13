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

function appendMessage(role, text) {
  var wrap = document.createElement("div");
  wrap.className = "message " + role;
  var bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  var meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = role === "user" ? "Вы" : "Бот";
  wrap.appendChild(bubble);
  wrap.appendChild(meta);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
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
    sourcesView.textContent = "Источники появятся после запроса";
    return;
  }
  items.forEach(function(item) {
    var block = document.createElement("div");
    block.className = "source-item";
    var title = document.createElement("div");
    title.className = "source-title";
    title.textContent = item.title + ", " + item.source + ", score " + item.score;
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
  traceLogView.textContent = JSON.stringify(compactTrace(debug), null, 2);
  chunksLogView.textContent = JSON.stringify(chunkTrace(debug), null, 2);
  payloadLogView.textContent = JSON.stringify(firstPayload(debug), null, 2);
}

function compactTrace(debug) {
  if (!debug) {
    return {status: "empty"};
  }
  var trace = {};
  ["status", "provider", "model", "base_url", "message", "validation", "models"].forEach(function(key) {
    if (debug[key] !== undefined) {
      trace[key] = debug[key];
    }
  });
  if (debug.rag) {
    trace.rag = {
      top_k: debug.rag.top_k,
      request_type: debug.rag.request_type,
      missing_fields: debug.rag.missing_fields || [],
      chunk_count: debug.rag.chunks ? debug.rag.chunks.length : 0
    };
  }
  trace.llm = (debug.llm || []).map(function(item) {
    return {
      purpose: item.purpose,
      status: item.status,
      fallback_used: item.fallback_used,
      provider: item.provider,
      model: item.model,
      endpoint: item.endpoint,
      options: item.options,
      response: item.response,
      error: item.error,
      eval_count: item.eval_count,
      prompt_eval_count: item.prompt_eval_count
    };
  });
  return trace;
}

function chunkTrace(debug) {
  if (!debug || !debug.rag || !debug.rag.chunks) {
    return [];
  }
  return debug.rag.chunks.map(function(chunk) {
    return {
      rank: chunk.rank,
      id: chunk.id,
      title: chunk.title,
      category: chunk.category,
      source: chunk.source,
      score: chunk.score,
      characters: chunk.characters,
      text: chunk.text
    };
  });
}

function firstPayload(debug) {
  if (!debug || !debug.llm || !debug.llm.length) {
    return {status: "empty", message: "LLM payload is not available yet"};
  }
  var trace = debug.llm[0];
  return {
    status: trace.status,
    fallback_used: trace.fallback_used,
    endpoint: trace.endpoint,
    model: trace.model,
    options: trace.options,
    payload: trace.payload,
    response: trace.response,
    error: trace.error,
    eval_count: trace.eval_count,
    prompt_eval_count: trace.prompt_eval_count
  };
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
    sourcesView.textContent = "Источники появятся после запроса";
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
