const API = "/api/v1";
const projectList = document.querySelector("#project-list");
const projectCount = document.querySelector("#project-count");
const apiStatus = document.querySelector("#api-status");
const apiDetail = document.querySelector("#api-detail");
const projectForm = document.querySelector("#project-form");
const formMessage = document.querySelector("#form-message");

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let message = "Não foi possível concluir a solicitação.";
    try {
      const payload = await response.json();
      message = payload.detail || message;
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
      <p>Cadastre seu primeiro projeto. A análise automática chegará em uma próxima fase.</p>
      <button class="primary-button" id="empty-create-project">Cadastrar primeiro projeto</button>
    </div>`;
    document.querySelector("#empty-create-project").addEventListener("click", openForm);
    return;
  }
  projectList.innerHTML = projects.map((project) => `<article class="project-card">
    <div class="project-symbol" aria-hidden="true">▧</div>
    <div class="project-info"><h3>${escapeHtml(project.name)}</h3>
    <p>${escapeHtml(project.description || "Sem descrição")}</p></div>
    <span class="project-status">Cadastrado</span>
  </article>`).join("");
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
  projectForm.classList.remove("hidden");
  projectForm.querySelector('input[name="name"]').focus();
}

document.querySelector("#open-project-form").addEventListener("click", openForm);
document.querySelector("#close-project-form").addEventListener("click", () => {
  projectForm.classList.add("hidden");
  formMessage.textContent = "";
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

checkApi();
loadProjects();
