const API = "/api/v1";
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
      <button class="small-button history-project">Histórico</button>${project.root_path ? '<button class="small-button agent-project">Pedir ao agente</button>' : ""}
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
          planBox.innerHTML = `<h4>${escapeHtml(plan.summary)}</h4><ol>${(plan.steps || []).map(step => `<li><b>${escapeHtml(step.title || "")}</b><p>${escapeHtml(step.description || "")}</p></li>`).join("")}</ol><h4>Arquivos propostos: ${(plan.proposed_changes || []).length}</h4><ul>\${(plan.proposed_changes || []).map(change => \`<li><b>\${escapeHtml(change.path)}</b> — \${escapeHtml(change.reason || "")}<pre>\${escapeHtml(change.content || "")}</pre></li>\`).join("") || "<li>Nenhum arquivo será alterado.</li>"}</ul><h4>Riscos</h4><ul>\${(plan.risks || []).map(risk => \`<li>\${escapeHtml(risk)}</li>\`).join("") || "<li>Nenhum risco informado pelo modelo.</li>"}</ul><p class="agent-warning">Revise o conteúdo completo de cada arquivo. Aprovar aplica as alterações exibidas.</p>\${(plan.proposed_changes || []).length ? '<button class="small-button approve-agent">Aprovar e aplicar</button>' : '<span>Não há alterações para aplicar.</span>'} <button class="small-button reject-agent">Rejeitar</button>`;
          planBox.querySelector(".approve-agent").addEventListener("click", async () => {
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
    apiStatus.textContent = "Offline";
    apiDetail.textContent = "Inicie o servidor local";
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

checkApi();
loadProjects();
