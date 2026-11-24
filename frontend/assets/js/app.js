const API = "/api/v1";
let authToken = sessionStorage.getItem("devpilotToken") || "";
const projectList = document.querySelector("#project-list");
const projectCount = document.querySelector("#project-count");
const apiStatus = document.querySelector("#api-status");
const apiDetail = document.querySelector("#api-detail");
const projectForm = document.querySelector("#project-form");
const importForm = document.querySelector("#import-form");
const formMessage = document.querySelector("#form-message");
const importMessage = document.querySelector("#import-message");

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

async function request(path, options = {}) {
  const headers = { ...options.headers };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    let message = "Não foi possível concluir a solicitação.";
    try {
      const payload = await response.json();
      message = payload.detail || message;
      if (Array.isArray(message)) message = message.map((item) => item.msg).join("; ");
    } catch { /* Resposta sem JSON: usa a mensagem padrão. */ }
    throw new Error(typeof message === "string" ? message : "Verifique os dados informados.");
  }
  return response.status === 204 ? null : response.json();
}

function renderProjects(projects) {
  projectCount.textContent = projects.length;
  if (!projects.length) {
    projectList.innerHTML = `<div class="empty-state">
      <strong>Seu espaço está pronto para começar.</strong>
      <p>Cadastre um projeto ou importe um ZIP para conhecer sua estrutura.</p>
      <button class="primary-button" id="empty-import-project">Importar primeiro projeto</button>
    </div>`;
    document.querySelector("#empty-import-project").addEventListener("click", openImportForm);
    return;
  }
  projectList.innerHTML = projects.map((project) => `<article class="project-card" data-project-id="${project.id}">
    <div class="project-symbol" aria-hidden="true">▧</div>
    <div class="project-info"><h3>${escapeHtml(project.name)}</h3>
    <p>${escapeHtml(project.description || "Sem descrição")}</p>
    <small class="project-meta">${project.root_path ? "Arquivos importados" : "Cadastro manual"} · ${escapeHtml(project.status)}</small></div>
    <div class="project-actions">
      ${project.root_path ? '<button class="small-button analyze-project">Analisar</button>' : ""}
      <button class="small-button history-project">Histórico</button>${project.root_path ? '<button class="small-button agent-project">Pedir ao agente</button><button class="small-button rescue-project">Modo Resgate</button><button class="small-button validate-project">Validar</button><button class="small-button memory-project">Memória</button>' : ""}
    </div>
  </article>`).join("");

  projectList.querySelectorAll(".analyze-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".project-card");
      const id = card.dataset.projectId;
      button.disabled = true;
      button.textContent = "Analisando…";
      try {
        const analysis = await request(`/projects/${id}/analyze`, { method: "POST" });
        showCardMessage(card, `Análise concluída: ${analysis.total_files} arquivos · ${analysis.detected_technologies.join(", ") || "tecnologias não identificadas"}`);
        await loadProjects();
      } catch (error) {
        showCardMessage(card, error.message, true);
      } finally {
        button.disabled = false;
        button.textContent = "Analisar";
      }
    });
  });

  projectList.querySelectorAll(".history-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".project-card");
      const id = card.dataset.projectId;
      button.disabled = true;
      try {
        const events = await request(`/projects/${id}/events`);
        const history = events.length
          ? events.map((event) => `<li><b>${escapeHtml(event.summary)}</b><small>${escapeHtml(new Date(event.created_at).toLocaleString("pt-BR"))}</small></li>`).join("")
          : "<li>Nenhum evento registrado.</li>";
        let panel = card.querySelector(".history-panel");
        if (!panel) {
          panel = document.createElement("div");
          panel.className = "history-panel";
          card.append(panel);
        }
        panel.innerHTML = `<ul>${history}</ul>`;
      } catch (error) {
        showCardMessage(card, error.message, true);
      } finally {
        button.disabled = false;
      }
    });
  });

  projectList.querySelectorAll(".agent-project").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".project-card");
      let panel = card.querySelector(".agent-panel");
      if (panel) { panel.remove(); return; }
      panel = document.createElement("div");
      panel.className = "agent-panel";
      panel.innerHTML = '<label>O que você quer que o agente faça?<textarea rows="3" minlength="8" maxlength="4000" placeholder="Ex.: analise o código e proponha uma melhoria para o tratamento de erros"></textarea></label><button class="small-button create-agent-task">Gerar plano</button><p class="agent-feedback" role="status"></p><div class="agent-plan"></div>';
      card.append(panel);
      panel.querySelector(".create-agent-task").addEventListener("click", async () => {
        const prompt = panel.querySelector("textarea").value.trim();
        const feedback = panel.querySelector(".agent-feedback");
        const submit = panel.querySelector(".create-agent-task");
        if (prompt.length < 8) { feedback.textContent = "Descreva a tarefa com pelo menos 8 caracteres."; return; }
        submit.disabled = true; submit.textContent = "Planejando…"; feedback.textContent = "";
        try {
          const task = await request(`/projects/${card.dataset.projectId}/tasks`, {method:"POST", body:JSON.stringify({instruction:prompt})});
          const plan = JSON.parse(task.plan_json);
          const planBox = panel.querySelector(".agent-plan");
          planBox.innerHTML = `<h4>${escapeHtml(plan.summary)}</h4><ol>${(plan.steps || []).map(step => `<li><b>${escapeHtml(step.title || "")}</b><p>${escapeHtml(step.description || "")}</p></li>`).join("")}</ol><h4>Arquivos propostos: ${(plan.proposed_changes || []).length}</h4><ul>${(plan.proposed_changes || []).map(change => "<li><b>" + escapeHtml(change.path) + "</b> — " + escapeHtml(change.reason || "") + "<pre>" + escapeHtml(change.content || "") + "</pre></li>").join("") || "<li>Nenhum arquivo será alterado.</li>"}</ul><h4>Riscos</h4><ul>${(plan.risks || []).map(risk => "<li>" + escapeHtml(risk) + "</li>").join("") || "<li>Nenhum risco informado pelo modelo.</li>"}</ul><p class="agent-warning">Revise o conteúdo completo de cada arquivo. Aprovar aplica as alterações exibidas.</p>${(plan.proposed_changes || []).length ? '<button class="small-button approve-agent">Aprovar e aplicar</button>' : '<span>Não há alterações para aplicar.</span>'} <button class="small-button reject-agent">Rejeitar</button>`;
          const approveButton = planBox.querySelector(".approve-agent");
          if (approveButton) approveButton.addEventListener("click", async () => {
            if (!confirm("Aplicar as alterações propostas nos arquivos deste projeto? Faça backup antes de continuar.")) return;
            try { await request(`/tasks/${task.id}/approve`, {method:"POST"}); feedback.textContent = "Alterações aplicadas. Revise os arquivos e faça os testes."; }
            catch (error) { feedback.textContent = error.message; }
          });
          planBox.querySelector(".reject-agent").addEventListener("click", async () => {
            try { await request(`/tasks/${task.id}/reject`, {method:"POST"}); feedback.textContent = "Plano rejeitado."; }
            catch (error) { feedback.textContent = error.message; }
          });
        } catch (error) { feedback.textContent = error.message; }
        finally { submit.disabled = false; submit.textContent = "Gerar plano"; }
      });
    });
  });


  projectList.querySelectorAll(".rescue-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".project-card"); button.disabled = true; button.textContent = "Diagnosticando…";
      try {
        const report = await request(`/projects/${card.dataset.projectId}/rescue`, {method:"POST"});
        const findings = report.findings.map(item => `<li><b>${escapeHtml(item.severity.toUpperCase())} · ${escapeHtml(item.title)}</b><p>${escapeHtml(item.detail)}</p><p>${escapeHtml(item.recommendation)}</p></li>`).join("");
        showCardMessage(card, `Modo Resgate: pontuação indicativa ${report.score}/100 · ${report.total_findings} achados. ${report.limitations.join(" ")}`);
        let panel = card.querySelector(".rescue-panel");
        if (!panel) { panel = document.createElement("div"); panel.className = "rescue-panel"; card.append(panel); }
        panel.innerHTML = `<h4>Diagnóstico estático</h4><ul>${findings || "<li>Nenhum achado nas verificações atuais.</li>"}</ul>`;
      } catch(error) { showCardMessage(card,error.message,true); }
      finally { button.disabled = false; button.textContent = "Modo Resgate"; }
    });
  });
  projectList.querySelectorAll(".validate-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".project-card"); button.disabled = true; button.textContent = "Testando…";
      try {
        const result = await request(`/projects/${card.dataset.projectId}/validate`, {method:"POST"});
        showCardMessage(card, `Testes: ${result.status} (código ${result.exit_code}). ${result.output || ""}`, result.status !== "passed");
      } catch(error) { showCardMessage(card,error.message,true); }
      finally { button.disabled = false; button.textContent = "Validar"; }
    });
  });
  projectList.querySelectorAll(".memory-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".project-card"); button.disabled = true;
      try {
        const entries = await request(`/projects/${card.dataset.projectId}/memory`);
        let panel = card.querySelector(".memory-panel");
        if (!panel) { panel = document.createElement("div"); panel.className = "memory-panel"; card.append(panel); }
        panel.innerHTML = `<h4>Memória técnica persistente</h4><ul>${entries.map(item => `<li><b>${escapeHtml(item.memory_key)}</b> <small>(${escapeHtml(item.source)})</small><pre>${escapeHtml(item.content)}</pre></li>`).join("") || "<li>Ainda sem memórias.</li>"}</ul><label>Chave <input class="memory-key" maxlength="120" placeholder="ex.: arquitetura"></label><label>Informação<textarea class="memory-content" maxlength="8000" rows="3" placeholder="Decisão técnica, padrão ou contexto importante"></textarea></label><button class="small-button save-memory">Salvar memória</button><p class="memory-feedback" role="status"></p>`;
        panel.querySelector(".save-memory").addEventListener("click", async () => {
          const key=panel.querySelector(".memory-key").value.trim(), content=panel.querySelector(".memory-content").value.trim(), feedback=panel.querySelector(".memory-feedback");
          try { await request(`/projects/${card.dataset.projectId}/memory`,{method:"PUT",body:JSON.stringify({memory_key:key,content})}); feedback.textContent="Memória salva."; panel.querySelector(".memory-key").value=""; panel.querySelector(".memory-content").value=""; }
          catch(error) { feedback.textContent=error.message; }
        });
      } catch(error) { showCardMessage(card,error.message,true); }
      finally { button.disabled = false; }
    });
  });

}


function renderAuthPanel() {
  projectList.innerHTML = '<section class="auth-panel"><h2>Acesse seu espaço</h2><p>Entre na sua conta ou crie uma conta gratuita para continuar.</p><form id="auth-form"><label>E-mail<input name="email" type="email" autocomplete="username" required></label><label>Senha<input name="password" type="password" minlength="12" autocomplete="current-password" required></label><p id="auth-message" role="status"></p><button class="primary-button" type="submit">Entrar</button></form><button class="text-button" id="auth-toggle" type="button">Criar uma conta</button></section>';
  let mode = "login";
  const form = document.querySelector("#auth-form");
  const toggle = document.querySelector("#auth-toggle");
  toggle.addEventListener("click", () => {
    mode = mode === "login" ? "register" : "login";
    form.querySelector('button[type="submit"]').textContent = mode === "login" ? "Entrar" : "Criar conta";
    form.querySelector('input[name="password"]').autocomplete = mode === "login" ? "current-password" : "new-password";
    toggle.textContent = mode === "login" ? "Criar uma conta" : "Já tenho uma conta";
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const message = document.querySelector("#auth-message");
    const payload = Object.fromEntries(new FormData(form).entries());
    button.disabled = true; message.textContent = "";
    try {
      const response = await fetch(`${API}/auth/${mode}`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Não foi possível autenticar.");
      authToken = data.access_token;
      document.querySelector("#logout").hidden = false;
      sessionStorage.setItem("devpilotToken", authToken);
      await loadProjects();
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; }
  });
}

function logout() {
  authToken = "";
  document.querySelector("#logout").hidden = true;
  sessionStorage.removeItem("devpilotToken");
  renderAuthPanel();
}

function showCardMessage(card, message, isError = false) {
  let panel = card.querySelector(".card-message");
  if (!panel) {
    panel = document.createElement("p");
    panel.className = "card-message";
    card.append(panel);
  }
  panel.textContent = message;
  panel.classList.toggle("error", isError);
}

async function loadProjects() {
  try {
    renderProjects(await request("/projects"));
  } catch (error) {
    if (error.message.includes("Autenticação necessária") || error.message.includes("Token inválido") || error.message.includes("Conta inativa")) { renderAuthPanel(); return; }
    projectList.innerHTML = '<div class="empty-state"><strong>Não foi possível carregar os projetos.</strong><p>Confira se a API está em execução e tente novamente.</p></div>';
    projectCount.textContent = "—";
    console.error(error);
  }
}

async function checkApi() {
  try {
    await request("/health");
    apiStatus.textContent = "Online";
    apiDetail.textContent = "API respondendo normalmente";
  } catch {
    apiStatus.textContent = authToken ? "Offline" : "Login";
    apiDetail.textContent = authToken ? "Inicie o servidor local" : "Autenticação necessária para consultar a API";
  }
}

function openForm() {
  importForm.classList.add("hidden");
  projectForm.classList.remove("hidden");
  projectForm.querySelector('input[name="name"]').focus();
}
function openImportForm() {
  projectForm.classList.add("hidden");
  importForm.classList.remove("hidden");
  importForm.querySelector('input[name="name"]').focus();
}

document.querySelector("#open-project-form").addEventListener("click", openForm);
document.querySelector("#open-import-form").addEventListener("click", openImportForm);
document.querySelector("#close-project-form").addEventListener("click", () => {
  projectForm.classList.add("hidden");
  formMessage.textContent = "";
});
document.querySelector("#close-import-form").addEventListener("click", () => {
  importForm.classList.add("hidden");
  importMessage.textContent = "";
});

projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = projectForm.querySelector('button[type="submit"]');
  const payload = Object.fromEntries(new FormData(projectForm).entries());
  for (const key of Object.keys(payload)) {
    if (!payload[key].trim()) payload[key] = null;
  }
  submitButton.disabled = true;
  submitButton.textContent = "Salvando…";
  formMessage.textContent = "";
  try {
    await request("/projects", { method: "POST", body: JSON.stringify(payload) });
    projectForm.reset();
    projectForm.classList.add("hidden");
    await loadProjects();
  } catch (error) {
    formMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Salvar projeto";
  }
});

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = importForm.querySelector('button[type="submit"]');
  const formData = new FormData(importForm);
  submitButton.disabled = true;
  submitButton.textContent = "Importando…";
  importMessage.textContent = "";
  try {
    await request("/projects/import", { method: "POST", body: formData });
    importForm.reset();
    importForm.classList.add("hidden");
    await loadProjects();
  } catch (error) {
    importMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = "Importar projeto";
  }
});

document.querySelector("#logout")?.addEventListener("click", logout);
if (authToken && document.querySelector("#logout")) document.querySelector("#logout").hidden = false;
checkApi();
loadProjects();
