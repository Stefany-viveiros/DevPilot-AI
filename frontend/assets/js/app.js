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
      <button class="small-button history-project">Histórico</button>${project.root_path ? '<button class="small-button tasks-project">Tarefas</button>' : ""}${project.root_path ? '<button class="small-button agent-project">Pedir ao agente</button><button class="small-button rescue-project">Modo Resgate</button><button class="small-button validate-project">Validar</button><button class="small-button repair-project">Testar + propor correção</button><button class="small-button memory-project">Memória</button>' : ""}
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
        const [events, runs] = await Promise.all([
          request(`/projects/${id}/events`),
          request(`/projects/${id}/runs`),
        ]);
        const history = events.length
          ? events.map((event) => `<li><b>${escapeHtml(event.summary)}</b><small>${escapeHtml(new Date(event.created_at).toLocaleString("pt-BR"))}</small></li>`).join("")
          : "<li>Nenhum evento registrado.</li>";
        const reports = runs.length
          ? runs.map((run) => `<li><b>${escapeHtml(run.run_type)} · ${escapeHtml(run.status)}</b><p>${escapeHtml(run.summary)}</p><small>${escapeHtml(new Date(run.created_at).toLocaleString("pt-BR"))}</small>${run.details ? `<details><summary>Ver evidências</summary><pre>${escapeHtml(JSON.stringify(run.details, null, 2))}</pre></details>` : ""}</li>`).join("")
          : "<li>Nenhuma execução registrada.</li>";
        let panel = card.querySelector(".history-panel");
        if (!panel) {
          panel = document.createElement("div");
          panel.className = "history-panel";
          card.append(panel);
        }
        panel.innerHTML = `<h4>Eventos do projeto</h4><ul>${history}</ul><h4>Execuções e evidências</h4><ul>${reports}</ul>`;
      } catch (error) {
        showCardMessage(card, error.message, true);
      } finally {
        button.disabled = false;
      }
    });
  });

  projectList.querySelectorAll(".tasks-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".project-card");
      button.disabled = true;
      try {
        const tasks = await request(`/projects/${card.dataset.projectId}/tasks`);
        let panel = card.querySelector(".tasks-panel");
        if (!panel) {
          panel = document.createElement("div");
          panel.className = "tasks-panel";
          card.append(panel);
        }
        const statusLabels = {
          awaiting_approval: "Aguardando aprovação",
          applied: "Aplicada",
          restored: "Restaurada",
          rejected: "Rejeitada",
        };
        panel.innerHTML = `<h4>Tarefas do agente</h4>${tasks.length ? tasks.map((task) => {
          let plan = {};
          try { plan = JSON.parse(task.plan_json || "{}"); } catch { plan = {}; }
          const changes = Array.isArray(plan.proposed_changes) ? plan.proposed_changes : [];
          let result = {};
          try { result = JSON.parse(task.result_json || "{}"); } catch { result = {}; }
          const filesWritten = Array.isArray(result.files_written) ? result.files_written : [];
          const status = statusLabels[task.status] || task.status;
          const controls = task.status === "applied"
            ? `<button class="small-button restore-task" data-task-id="${task.id}">Restaurar versão anterior</button>`
            : task.status === "awaiting_approval"
              ? `<button class="small-button diff-task" data-task-id="${task.id}">Ver diferenças</button><button class="small-button approve-task" data-task-id="${task.id}">Aprovar e aplicar</button><button class="small-button reject-task" data-task-id="${task.id}">Rejeitar</button>`
              : "";
          return `<article class="task-item"><div class="task-heading"><b>#${task.id} · ${escapeHtml(status)}</b><small>${escapeHtml(new Date(task.created_at).toLocaleString("pt-BR"))}</small></div><p>${escapeHtml(task.instruction)}</p><p>${escapeHtml(plan.summary || "Plano indisponível")}</p><small>${changes.length} arquivo(s) no plano</small>${filesWritten.length ? `<details><summary>Arquivos aplicados (${filesWritten.length})</summary><ul>${filesWritten.map(path => `<li>${escapeHtml(path)}</li>`).join("")}</ul></details>` : ""}<div class="task-controls">${controls}</div></article>`;
        }).join("") : "<p>Nenhuma tarefa criada para este projeto.</p>"}<p class="task-feedback" role="status"></p><p class="agent-warning">Restaurar substitui os arquivos alterados pela cópia de segurança anterior à tarefa. Faça isso somente se tiver certeza.</p>`;
        const feedback = panel.querySelector(".task-feedback");
        panel.querySelectorAll(".diff-task").forEach((action) => action.addEventListener("click", async () => {
          action.disabled = true;
          try {
            const preview = await request(`/tasks/${action.dataset.taskId}/diff`);
            const taskItem = action.closest(".task-item");
            let diffPanel = taskItem.querySelector(".task-diff");
            if (!diffPanel) {
              diffPanel = document.createElement("div");
              diffPanel.className = "task-diff";
              taskItem.append(diffPanel);
            }
            diffPanel.innerHTML = preview.files.map(file => `<section><b>${escapeHtml(file.path)} ${file.is_new ? "(novo arquivo)" : ""}</b><pre>${escapeHtml(file.diff || "Nenhuma diferença textual.")}</pre></section>`).join("");
          } catch (error) { feedback.textContent = error.message; }
          finally { action.disabled = false; }
        }));
        panel.querySelectorAll(".approve-task").forEach((action) => action.addEventListener("click", async () => {
          if (!confirm("Aplicar as alterações desta tarefa? O DevPilot criará um checkpoint antes de gravar.")) return;
          action.disabled = true;
          try {
            await request(`/tasks/${action.dataset.taskId}/approve`, {method:"POST"});
            feedback.textContent = "Alterações aplicadas e checkpoint criado.";
            button.disabled = false;
            button.click();
          } catch (error) { feedback.textContent = error.message; action.disabled = false; }
        }));
        panel.querySelectorAll(".reject-task").forEach((action) => action.addEventListener("click", async () => {
          if (!confirm("Rejeitar este plano?")) return;
          action.disabled = true;
          try {
            await request(`/tasks/${action.dataset.taskId}/reject`, {method:"POST"});
            feedback.textContent = "Plano rejeitado.";
            button.disabled = false;
            button.click();
          } catch (error) { feedback.textContent = error.message; action.disabled = false; }
        }));
        panel.querySelectorAll(".restore-task").forEach((action) => action.addEventListener("click", async () => {
          if (!confirm("Restaurar os arquivos para o estado anterior à aplicação desta tarefa? Esta ação substitui os arquivos atuais.")) return;
          action.disabled = true;
          try {
            await request(`/tasks/${action.dataset.taskId}/restore`, {method:"POST"});
            feedback.textContent = "Checkpoint restaurado. Confira os arquivos do projeto.";
            button.disabled = false;
            button.click();
          } catch (error) { feedback.textContent = error.message; action.disabled = false; }
        }));
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
          await loadAccount();
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
        const checkLabels = {python_syntax:"Sintaxe Python", pytest:"Testes Python", javascript_syntax:"Sintaxe JavaScript", typescript_syntax:"Sintaxe TypeScript/JSX"};
        const checksSummary = (result.checks || []).map((check) => `${checkLabels[check.name] || check.name}: ${check.status}`).join(" · ");
        const statusLabels = {passed:"aprovado", failed:"falhou", timeout:"tempo esgotado", inconclusive:"inconclusivo", not_applicable:"sem verificações aplicáveis"};
        showCardMessage(card, `Validação: ${statusLabels[result.status] || result.status}. ${checksSummary}. ${result.output || ""}`, !["passed","not_applicable"].includes(result.status));
      } catch(error) { showCardMessage(card,error.message,true); }
      finally { button.disabled = false; button.textContent = "Validar"; }
    });
  });

  projectList.querySelectorAll(".repair-project").forEach((button) => {
    button.addEventListener("click", async () => {
      const card=button.closest(".project-card"); button.disabled=true; button.textContent="Testando…";
      try {
        const result=await request(`/projects/${card.dataset.projectId}/repair`,{method:"POST"});
        await loadAccount();
        showCardMessage(card,`Validação: ${result.validation.status}. ${result.validation.output || ""}`,result.validation.status!=="passed");
        let panel=card.querySelector(".repair-panel");
        if (!panel) { panel=document.createElement("div"); panel.className="repair-panel"; card.append(panel); }
        if (!result.task) { panel.textContent=result.planning_error || "Nenhuma correção necessária."; return; }
        const plan=result.task.plan;
        panel.innerHTML=`<h4>Proposta aguardando aprovação</h4><p>${escapeHtml(plan.summary)}</p><ul>${(plan.proposed_changes||[]).map(change=>"<li><b>"+escapeHtml(change.path)+"</b><pre>"+escapeHtml(change.content||"")+"</pre></li>").join("")||"<li>Sem alterações propostas.</li>"}</ul><p class="agent-warning">Os testes falharam. Revise o conteúdo antes de aprovar.</p>${(plan.proposed_changes||[]).length?'<button class="small-button approve-repair">Aprovar correção</button>':'<span>Não há alterações para aplicar.</span>'} <button class="small-button reject-repair">Rejeitar</button><p class="repair-feedback" role="status"></p>`;
        const approve=panel.querySelector(".approve-repair");
        if(approve) approve.addEventListener("click",async()=>{
          if(!confirm("Aplicar a correção proposta? Faça backup antes de continuar.")) return;
          try { await request(`/tasks/${result.task.id}/approve`,{method:"POST"}); panel.querySelector(".repair-feedback").textContent="Correção aplicada. Execute Validar novamente para conferir o resultado."; }
          catch(error){panel.querySelector(".repair-feedback").textContent=error.message;}
        });
        panel.querySelector(".reject-repair").addEventListener("click",async()=>{
          try { await request(`/tasks/${result.task.id}/reject`,{method:"POST"}); panel.querySelector(".repair-feedback").textContent="Proposta rejeitada."; }
          catch(error){panel.querySelector(".repair-feedback").textContent=error.message;}
        });
      } catch(error){showCardMessage(card,error.message,true);}
      finally{button.disabled=false;button.textContent="Testar + propor correção";}
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

async function loadAccount() {
  const usage = document.querySelector("#account-usage");
  if (!usage) return;
  try {
    const account = await request("/auth/me");
    usage.textContent = `${account.email} · Projetos ${account.projects_used}/${account.projects_limit} · IA/24h ${account.tasks_used_today}/${account.tasks_limit}`;
    usage.hidden = false;
  } catch {
    usage.hidden = true;
  }
}

function logout() {
  authToken = "";
  document.querySelector("#logout").hidden = true;
  const usage = document.querySelector("#account-usage");
  if (usage) usage.hidden = true;
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
    const projects = await request("/projects");
    renderProjects(projects);
    if (authToken) await loadAccount();
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
