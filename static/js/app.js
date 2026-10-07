/**
 * PDF Voice AI – Projects → Notebooks → Files + Voice
 */
(function () {
  "use strict";

  const state = {
    apiKey: localStorage.getItem("pva_api_key") || "",
    provider: localStorage.getItem("pva_provider") || "gemini",
    rackId: localStorage.getItem("pva_rack_id") || "",
    racks: [],
    selectedFile: null,
    isListening: false,
    isSpeaking: false,
    isBusy: false,
    language: navigator.language || "es-ES",
    audioUnlocked: false,
    editingRackId: null,
    editingNbId: null,
  };

  const $ = (s) => document.querySelector(s);
  const providerSelect = $("#providerSelect");
  const apiKeyInput = $("#apiKeyInput");
  const toggleKeyBtn = $("#toggleKeyBtn");
  const fileInput = $("#fileInput");
  const uploadBtn = $("#uploadBtn");
  const fileName = $("#fileName");
  const indexBtn = $("#indexBtn");
  const uploadProgress = $("#uploadProgress");
  const chatMessages = $("#chatMessages");
  const textInput = $("#textInput");
  const sendBtn = $("#sendBtn");
  const voiceBtn = $("#voiceBtn");
  const voiceStatus = $("#voiceStatus");
  const statusBadge = $("#statusBadge");
  const detectedLang = $("#detectedLang");
  const rackSelect = $("#rackSelect");
  const newRackBtn = $("#newRackBtn");
  const editRackBtn = $("#editRackBtn");
  const rackIcon = $("#rackIcon");
  const rackName = $("#rackName");
  const rackDesc = $("#rackDesc");
  const docCount = $("#docCount");
  const notebooksList = $("#notebooksList");
  const newNbBtn = $("#newNbBtn");
  const uploadNbSelect = $("#uploadNbSelect");

  const rackModal = $("#rackModal");
  const rmName = $("#rmName");
  const rmIcon = $("#rmIcon");
  const rmDesc = $("#rmDesc");
  const rmSystem = $("#rmSystem");
  const rmOperating = $("#rmOperating");
  const rmCancel = $("#rmCancel");
  const rmSave = $("#rmSave");
  const rackModalTitle = $("#rackModalTitle");

  const nbModal = $("#nbModal");
  const nbName = $("#nbName");
  const nbDomain = $("#nbDomain");
  const nbDesc = $("#nbDesc");
  const nbCancel = $("#nbCancel");
  const nbSave = $("#nbSave");
  const nbModalTitle = $("#nbModalTitle");

  detectedLang.textContent = state.language;
  providerSelect.value = state.provider;
  apiKeyInput.value = state.apiKey;

  providerSelect.addEventListener("change", () => {
    state.provider = providerSelect.value;
    localStorage.setItem("pva_provider", state.provider);
  });
  apiKeyInput.addEventListener("input", () => {
    state.apiKey = apiKeyInput.value.trim();
    localStorage.setItem("pva_api_key", state.apiKey);
  });
  toggleKeyBtn.addEventListener("click", () => {
    apiKeyInput.type = apiKeyInput.type === "password" ? "text" : "password";
  });

  async function loadRacks() {
    try {
      const res = await fetch("/api/racks");
      state.racks = await res.json();
      renderRackSelect();
      if (state.rackId && state.racks.find((r) => r.id === state.rackId)) {
        rackSelect.value = state.rackId;
      } else if (state.racks.length) {
        state.rackId = state.racks[0].id;
        rackSelect.value = state.rackId;
        localStorage.setItem("pva_rack_id", state.rackId);
      }
      updateRackInfo();
      renderNotebooks();
    } catch {
      setStatus("Error cargando proyectos", "error");
    }
  }

  function currentRack() {
    return state.racks.find((r) => r.id === state.rackId) || null;
  }

  function renderRackSelect() {
    rackSelect.innerHTML = "";
    if (!state.racks.length) {
      rackSelect.innerHTML = '<option value="">— Sin proyectos —</option>';
      return;
    }
    state.racks.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.id;
      opt.textContent = `${r.icon || "📦"} ${r.name} (${r.document_count} docs)`;
      rackSelect.appendChild(opt);
    });
  }

  function updateRackInfo() {
    const r = currentRack();
    if (!r) {
      rackIcon.textContent = "📦";
      rackName.textContent = "Ningún proyecto";
      rackDesc.textContent = "Crea un proyecto para empezar";
      docCount.textContent = "0 docs";
      if (typeof refreshProjectPreview === "function") refreshProjectPreview();
      return;
    }
    rackIcon.textContent = r.icon || "📦";
    rackName.textContent = r.name;
    rackDesc.textContent = r.description || "Sin descripción";
    docCount.textContent = `${r.document_count} docs`;
    if (typeof refreshProjectPreview === "function") refreshProjectPreview();
  }

  rackSelect.addEventListener("change", () => {
    state.rackId = rackSelect.value;
    localStorage.setItem("pva_rack_id", state.rackId);
    updateRackInfo();
    renderNotebooks();
    const r = currentRack();
    if (r) {
      addSystemMessage(`🔄 Proyecto activo: <strong>${r.name}</strong> (${r.notebooks.length} cuadernos).`);
    }
  });

  newRackBtn.addEventListener("click", () => openRackModal(null));
  editRackBtn.addEventListener("click", () => {
    if (state.rackId) openRackModal(state.rackId);
  });
  rmCancel.addEventListener("click", () => rackModal.classList.add("hidden"));
  rackModal.addEventListener("click", (e) => {
    if (e.target === rackModal) rackModal.classList.add("hidden");
  });

  function openRackModal(id) {
    state.editingRackId = id;
    if (id) {
      const r = state.racks.find((x) => x.id === id);
      rackModalTitle.textContent = "Editar Proyecto";
      rmName.value = r?.name || "";
      rmIcon.value = r?.icon || "📦";
      rmDesc.value = r?.description || "";
      rmSystem.value = r?.system_instruction || "";
      rmOperating.value = r?.operating_instruction || "";
    } else {
      rackModalTitle.textContent = "Nuevo Proyecto";
      rmName.value = "";
      rmIcon.value = "📦";
      rmDesc.value = "";
      rmSystem.value = "";
      rmOperating.value = "";
    }
    rackModal.classList.remove("hidden");
    rmName.focus();
  }

  rmSave.addEventListener("click", async () => {
    const name = rmName.value.trim();
    if (!name) return alert("El nombre es obligatorio");
    const payload = {
      name,
      icon: rmIcon.value.trim() || "📦",
      description: rmDesc.value.trim(),
      system_instruction: rmSystem.value.trim(),
      operating_instruction: rmOperating.value.trim(),
    };
    try {
      setBusy(true);
      const isEdit = !!state.editingRackId;
      const res = await fetch(isEdit ? `/api/racks/${state.editingRackId}` : "/api/racks", {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error");
      rackModal.classList.add("hidden");
      await loadRacks();
      state.rackId = data.id;
      rackSelect.value = data.id;
      localStorage.setItem("pva_rack_id", data.id);
      updateRackInfo();
      renderNotebooks();
      addSystemMessage(`${isEdit ? "✏️" : "✅"} Proyecto <strong>${data.name}</strong> ${isEdit ? "actualizado" : "creado"}.`);
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  });

  function renderNotebooks() {
    const r = currentRack();
    notebooksList.innerHTML = "";
    uploadNbSelect.innerHTML = '<option value="">— Selecciona cuaderno —</option>';
    if (!r || !r.notebooks.length) {
      notebooksList.innerHTML = '<span style="font-size:0.8rem;color:var(--text-muted)">Sin cuadernos. Crea uno.</span>';
      return;
    }
    r.notebooks.forEach((nb) => {
      const chip = document.createElement("div");
      chip.className = "nb-chip";
      chip.innerHTML = `
        <span title="${escapeHtml(nb.domain || nb.description || "")}">${escapeHtml(nb.name)}</span>
        <span class="nb-count">${nb.document_count}</span>
        <button class="nb-del" data-id="${nb.id}" title="Eliminar">×</button>
      `;
      notebooksList.appendChild(chip);
      const opt = document.createElement("option");
      opt.value = nb.id;
      opt.textContent = `${nb.name} (${nb.document_count} docs)`;
      uploadNbSelect.appendChild(opt);
    });
    notebooksList.querySelectorAll(".nb-del").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const nid = btn.dataset.id;
        if (!confirm("¿Eliminar este cuaderno y todos sus archivos?")) return;
        try {
          const res = await fetch(`/api/racks/${state.rackId}/notebooks/${nid}`, { method: "DELETE" });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Error");
          await loadRacks();
          addSystemMessage(`🗑️ Cuaderno eliminado.`);
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }

  newNbBtn.addEventListener("click", () => {
    if (!state.rackId) return alert("Selecciona un proyecto primero");
    state.editingNbId = null;
    nbModalTitle.textContent = "Nuevo Cuaderno";
    nbName.value = "";
    nbDomain.value = "";
    nbDesc.value = "";
    nbModal.classList.remove("hidden");
    nbName.focus();
  });
  nbCancel.addEventListener("click", () => nbModal.classList.add("hidden"));
  nbModal.addEventListener("click", (e) => {
    if (e.target === nbModal) nbModal.classList.add("hidden");
  });

  nbSave.addEventListener("click", async () => {
    const name = nbName.value.trim();
    if (!name) return alert("El nombre es obligatorio");
    const payload = { name, domain: nbDomain.value.trim(), description: nbDesc.value.trim() };
    try {
      setBusy(true);
      const res = await fetch(`/api/racks/${state.rackId}/notebooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error");
      nbModal.classList.add("hidden");
      await loadRacks();
      addSystemMessage(`📓 Cuaderno <strong>${data.name}</strong> creado.`);
    } catch (err) {
      alert(err.message);
    } finally {
      setBusy(false);
    }
  });

  uploadBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    if (!f) return;
    state.selectedFile = f;
    fileName.textContent = f.name;
    indexBtn.disabled = !uploadNbSelect.value;
  });
  uploadNbSelect.addEventListener("change", () => {
    indexBtn.disabled = !state.selectedFile || !uploadNbSelect.value;
  });

  indexBtn.addEventListener("click", async () => {
    const nbId = uploadNbSelect.value;
    if (!state.selectedFile || !state.rackId || !nbId || state.isBusy) return;
    setBusy(true);
    setStatus("Indexando…", "loading");
    uploadProgress.classList.remove("hidden");
    const form = new FormData();
    form.append("file", state.selectedFile);
    try {
      const res = await fetch(`/api/racks/${state.rackId}/notebooks/${nbId}/upload`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al subir");
      addSystemMessage(`✅ <strong>${data.filename}</strong> → ${data.chunks} fragmentos en el cuaderno.`);
      setStatus("Documento listo", "ok");
      state.selectedFile = null;
      fileName.textContent = "Ningún archivo";
      indexBtn.disabled = true;
      fileInput.value = "";
      await loadRacks();
    } catch (err) {
      addSystemMessage(`❌ Error: ${err.message}`);
      setStatus("Error", "error");
    } finally {
      setBusy(false);
      uploadProgress.classList.add("hidden");
    }
  });

  sendBtn.addEventListener("click", () => sendMessage());
  textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage(overrideText) {
    const query = (overrideText || textInput.value).trim();
    if (!query || state.isBusy) return;
    if (!state.rackId) {
      addSystemMessage("⚠️ Selecciona o crea un proyecto primero.");
      return;
    }
    if (!state.apiKey) {
      addSystemMessage("⚠️ Introduce tu API Key.");
      return;
    }
    textInput.value = "";
    addMessage("user", query);
    setBusy(true);
    setStatus("Pensando…", "loading");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          rack_id: state.rackId,
          provider: state.provider,
          api_key: state.apiKey,
          language: state.language,
          temperature: 0.3,
          max_tokens: 2048,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error del servidor");
      addMessage("assistant", data.answer, {
        provider: data.provider,
        model: data.model,
        rack: data.rack_name,
        notebooks: data.notebooks_used,
        sources: data.sources,
        tokens: data.tokens_used,
      });
      setStatus("Listo", "ok");
      speak(data.answer);
    } catch (err) {
      addSystemMessage(`❌ ${err.message}`);
      setStatus("Error", "error");
    } finally {
      setBusy(false);
    }
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = state.language;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      state.isListening = true;
      voiceBtn.classList.add("listening");
      voiceStatus.textContent = "Escuchando…";
      setStatus("Escuchando", "loading");
    };
    recognition.onresult = (event) => {
      let interim = "", final = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += t;
        else interim += t;
      }
      if (interim) voiceStatus.textContent = interim;
      if (final) {
        voiceStatus.textContent = "";
        sendMessage(final.trim());
      }
    };
    recognition.onerror = (event) => {
      let msg = "Error de reconocimiento";
      if (event.error === "not-allowed") msg = "Micrófono denegado";
      else if (event.error === "no-speech") msg = "No se detectó voz";
      voiceStatus.textContent = msg;
      stopListening();
    };
    recognition.onend = () => stopListening();
  } else {
    voiceBtn.disabled = true;
  }

  voiceBtn.addEventListener("click", () => {
    unlockAudio();
    if (!recognition) return;
    if (state.isListening) {
      recognition.stop();
      return;
    }
    window.speechSynthesis.cancel();
    try {
      recognition.lang = state.language;
      recognition.start();
    } catch (e) {
      console.warn(e);
    }
  });

  function stopListening() {
    state.isListening = false;
    voiceBtn.classList.remove("listening");
    if (!voiceStatus.textContent.includes("denegado") && !voiceStatus.textContent.startsWith("Error")) {
      voiceStatus.textContent = "";
    }
    if (!state.isBusy) setStatus("Listo", "ok");
  }

  function speak(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = state.language;
    const voices = window.speechSynthesis.getVoices();
    const match = voices.find((v) => v.lang.startsWith(state.language.split("-")[0]));
    if (match) utter.voice = match;
    setTimeout(() => window.speechSynthesis.speak(utter), 50);
  }
  if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = () => {};

  function unlockAudio() {
    if (state.audioUnlocked) return;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) {
        const ctx = new Ctx();
        const buf = ctx.createBuffer(1, 1, 22050);
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        src.start(0);
        if (ctx.state === "suspended") ctx.resume();
      }
      if (window.speechSynthesis) {
        const s = new SpeechSynthesisUtterance("");
        s.volume = 0;
        window.speechSynthesis.speak(s);
      }
      state.audioUnlocked = true;
    } catch (e) {
      console.warn(e);
    }
  }
  ["touchstart", "click"].forEach((evt) => {
    document.addEventListener(evt, unlockAudio, { once: true, passive: true });
  });

  function addMessage(role, text, meta = null) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
    if (meta) {
      const metaEl = document.createElement("div");
      metaEl.className = "meta";
      metaEl.innerHTML = [
        meta.rack ? `<span>🎯 ${meta.rack}</span>` : "",
        meta.notebooks && meta.notebooks.length ? `<span>📓 ${meta.notebooks.join(", ")}</span>` : "",
        meta.provider ? `<span>${meta.provider}</span>` : "",
        meta.tokens != null ? `<span>${meta.tokens} tok</span>` : "",
      ].filter(Boolean).join(" · ");
      bubble.appendChild(metaEl);
      if (meta.sources && meta.sources.length) {
        const src = document.createElement("div");
        src.className = "sources";
        src.textContent = "Fuentes: " + meta.sources.join(", ");
        bubble.appendChild(src);
      }
    }
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function addSystemMessage(html) {
    const div = document.createElement("div");
    div.className = "message system";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = html;
    div.appendChild(bubble);
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  function setStatus(text, type = "ok") {
    statusBadge.textContent = text;
    statusBadge.className = "header-status" + (type !== "ok" ? ` ${type}` : "");
  }

  function setBusy(busy) {
    state.isBusy = busy;
    sendBtn.disabled = busy;
    indexBtn.disabled = busy || !state.selectedFile || !uploadNbSelect.value;
    textInput.disabled = busy;
  }

  const templatesBtn = $("#templatesBtn");
  const tplModal = $("#tplModal");
  const tplList = $("#tplList");
  const tplCancel = $("#tplCancel");
  const genBrief = $("#genBrief");
  const genNbCount = $("#genNbCount");
  const genBtn = $("#genBtn");

  if (templatesBtn) {
    templatesBtn.addEventListener("click", async () => {
      tplModal.classList.remove("hidden");
      await loadTemplates();
    });
  }
  if (tplCancel) tplCancel.addEventListener("click", () => tplModal.classList.add("hidden"));
  if (tplModal) {
    tplModal.addEventListener("click", (e) => {
      if (e.target === tplModal) tplModal.classList.add("hidden");
    });
  }

  async function loadTemplates() {
    try {
      const res = await fetch("/api/templates");
      const list = await res.json();
      tplList.innerHTML = "";
      if (!list.length) {
        tplList.innerHTML = "<p style='color:var(--text-muted)'>No hay plantillas.</p>";
        return;
      }
      list.forEach((t) => {
        const card = document.createElement("div");
        card.className = "tpl-card";
        card.innerHTML = `
          <span class="tpl-icon">${t.icon || "📦"}</span>
          <div class="tpl-body">
            <strong>${escapeHtml(t.name)}</strong>
            <p>${escapeHtml(t.description)}</p>
            <p>${t.notebook_count} cuadernos · ${escapeHtml(t.category)}</p>
          </div>
          <button type="button" class="btn btn-primary tpl-use" data-id="${t.id}">Usar</button>
        `;
        tplList.appendChild(card);
      });
      tplList.querySelectorAll(".tpl-use").forEach((btn) => {
        btn.addEventListener("click", () => instantiateTemplate(btn.dataset.id));
      });
    } catch (e) {
      tplList.innerHTML = `<p style="color:var(--danger)">Error: ${e.message}</p>`;
    }
  }

  async function instantiateTemplate(templateId) {
    try {
      setBusy(true);
      setStatus("Creando desde plantilla…", "loading");
      const res = await fetch(`/api/templates/${templateId}/instantiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed_documents: true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error");
      tplModal.classList.add("hidden");
      await loadRacks();
      state.rackId = data.project.id;
      rackSelect.value = data.project.id;
      localStorage.setItem("pva_rack_id", data.project.id);
      updateRackInfo();
      renderNotebooks();
      addSystemMessage(`📋 Proyecto <strong>${escapeHtml(data.project.name)}</strong> creado desde plantilla con ${data.project.notebooks.length} cuadernos y documentos semilla.`);
      setStatus("Listo", "ok");
    } catch (err) {
      alert(err.message);
      setStatus("Error", "error");
    } finally {
      setBusy(false);
    }
  }

  if (genBtn) {
    genBtn.addEventListener("click", async () => {
      const brief = (genBrief.value || "").trim();
      if (brief.length < 10) return alert("Describe el proyecto con al menos 10 caracteres");
      if (!state.apiKey) return alert("Necesitas una API Key del proveedor para generar con IA");
      try {
        setBusy(true);
        setStatus("Generando con IA…", "loading");
        const res = await fetch("/api/projects/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            brief,
            provider: state.provider,
            api_key: state.apiKey,
            language: state.language.split("-")[0] || "es",
            num_notebooks: parseInt(genNbCount.value, 10) || 3,
            seed_documents: true,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error");
        tplModal.classList.add("hidden");
        await loadRacks();
        state.rackId = data.project.id;
        rackSelect.value = data.project.id;
        localStorage.setItem("pva_rack_id", data.project.id);
        updateRackInfo();
        renderNotebooks();
        addSystemMessage(`✨ Proyecto <strong>${escapeHtml(data.project.name)}</strong> generado con IA (${data.project.notebooks.length} cuadernos).`);
        setStatus("Listo", "ok");
      } catch (err) {
        alert(err.message);
        setStatus("Error", "error");
      } finally {
        setBusy(false);
      }
    });
  }

  const previewBtn = $("#previewBtn");
  const sidePreview = $("#sidePreview");
  const sideBackdrop = $("#sideBackdrop");
  const pvClose = $("#pvClose");
  const pvEdit = $("#pvEdit");
  const pvChat = $("#pvChat");

  const SAMPLE_QUESTIONS = {
    "vet-avicola": [
      "Tengo 200 pollos de 10 días; ¿qué vacuna toca y cómo preparo el agua?",
      "Se humedeció la cama y bajó el consumo; ¿qué reviso primero?",
      "Arma el checklist diario para el lote de 200 aves.",
    ],
    "consejero-juridico": [
      "¿Qué cláusulas debo revisar primero en un contrato de servicios?",
      "¿Qué documentos guardar ante un despido?",
    ],
    "nutricionista": [
      "Necesito macros orientativos para hipertrofia, 75 kg, 4 entrenos/semana.",
      "¿Qué como 2 horas antes de entrenar fuerza?",
    ],
    "mantenimiento": [
      "Pasos de LOTO antes de cambiar un motor.",
      "El motor se calienta y el térmico dispara; ¿qué reviso?",
    ],
    "default": [
      "Resume qué sabe hacer este proyecto y qué cuadernos usa.",
      "Dame un ejemplo de pregunta que este proyecto pueda responder bien.",
      "¿Qué información debería subir a cada cuaderno?",
    ],
  };

  function samplesForRack(rack) {
    if (!rack) return SAMPLE_QUESTIONS.default;
    const id = (rack.id || "").toLowerCase();
    const name = (rack.name || "").toLowerCase();
    if (id.includes("vet") || name.includes("veterinar") || name.includes("avícola") || name.includes("avicola"))
      return SAMPLE_QUESTIONS["vet-avicola"];
    if (id.includes("jurid") || name.includes("juríd") || name.includes("legal"))
      return SAMPLE_QUESTIONS["consejero-juridico"];
    if (id.includes("nutri") || name.includes("nutri"))
      return SAMPLE_QUESTIONS["nutricionista"];
    if (id.includes("manten") || name.includes("manten") || name.includes("industrial"))
      return SAMPLE_QUESTIONS["mantenimiento"];
    return SAMPLE_QUESTIONS.default;
  }

  function isMobilePreview() {
    return window.matchMedia("(max-width: 899px)").matches;
  }

  function setPanelOpen(open) {
    if (!sidePreview) return;
    if (open) {
      sidePreview.classList.add("open");
      if (isMobilePreview() && sideBackdrop) sideBackdrop.classList.remove("hidden");
      else if (sideBackdrop) sideBackdrop.classList.add("hidden");
      localStorage.setItem("pva_panel_open", "1");
    } else {
      sidePreview.classList.remove("open");
      if (sideBackdrop) sideBackdrop.classList.add("hidden");
      localStorage.setItem("pva_panel_open", "0");
    }
  }

  function togglePanel() {
    const open = sidePreview && sidePreview.classList.contains("open");
    setPanelOpen(!open);
  }

  function refreshProjectPreview() {
    const r = currentRack();
    const icon = $("#pvIcon");
    const name = $("#pvName");
    const desc = $("#pvDesc");
    if (!icon) return;
    if (!r) {
      icon.textContent = "📦";
      name.textContent = "Sin proyecto";
      desc.textContent = "Selecciona o crea un proyecto";
      $("#pvDocs").textContent = "0 docs";
      $("#pvNbCount").textContent = "0 cuadernos";
      $("#pvId").textContent = "—";
      $("#pvSystem").textContent = "(Sin proyecto seleccionado)";
      $("#pvOperating").textContent = "(Sin proyecto seleccionado)";
      $("#pvNotebooks").innerHTML = "";
      $("#pvSamples").innerHTML = "";
      return;
    }
    icon.textContent = r.icon || "📦";
    name.textContent = r.name || "Proyecto";
    desc.textContent = r.description || "Sin descripción";
    $("#pvDocs").textContent = `${r.document_count || 0} docs indexados`;
    $("#pvNbCount").textContent = `${(r.notebooks || []).length} cuadernos`;
    $("#pvId").textContent = `id: ${r.id}`;
    $("#pvSystem").textContent = r.system_instruction || "(Sin instrucción de persona)";
    $("#pvOperating").textContent = r.operating_instruction || "(Sin instrucción de funcionamiento)";
    const nbBox = $("#pvNotebooks");
    nbBox.innerHTML = "";
    if (!r.notebooks || !r.notebooks.length) {
      nbBox.innerHTML = '<p style="font-size:0.85rem;color:var(--text-muted)">Sin cuadernos aún.</p>';
    } else {
      r.notebooks.forEach((nb) => {
        const card = document.createElement("div");
        card.className = "pv-nb-card";
        card.innerHTML = `
          <strong>${escapeHtml(nb.name)}</strong>
          <div class="pv-nb-meta">
            ${escapeHtml(nb.domain || "Sin dominio")} · ${nb.document_count || 0} docs
            ${nb.description ? " · " + escapeHtml(nb.description) : ""}
          </div>
        `;
        nbBox.appendChild(card);
      });
    }
    const samplesBox = $("#pvSamples");
    samplesBox.innerHTML = "";
    samplesForRack(r).forEach((q) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pv-sample";
      btn.textContent = q;
      btn.addEventListener("click", () => {
        if (isMobilePreview()) setPanelOpen(false);
        textInput.value = q;
        textInput.focus();
      });
      samplesBox.appendChild(btn);
    });
  }

  function openProjectPreview() {
    refreshProjectPreview();
    setPanelOpen(true);
  }

  if (previewBtn) {
    previewBtn.addEventListener("click", () => {
      refreshProjectPreview();
      togglePanel();
    });
  }
  if (pvClose) pvClose.addEventListener("click", () => setPanelOpen(false));
  if (sideBackdrop) sideBackdrop.addEventListener("click", () => setPanelOpen(false));
  if (pvEdit) {
    pvEdit.addEventListener("click", () => {
      if (isMobilePreview()) setPanelOpen(false);
      if (state.rackId) openRackModal(state.rackId);
    });
  }
  if (pvChat) {
    pvChat.addEventListener("click", () => {
      if (isMobilePreview()) setPanelOpen(false);
      textInput.focus();
    });
  }

  (function initPanelState() {
    const saved = localStorage.getItem("pva_panel_open");
    if (saved === "0") setPanelOpen(false);
    else setPanelOpen(true);
  })();

  loadRacks();
})();
