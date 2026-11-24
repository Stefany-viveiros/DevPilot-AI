from io import BytesIO
from zipfile import ZipFile

def make_zip(files: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()

def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "DevPilot AI"}

def test_create_and_list_projects(client):
    created = client.post("/api/v1/projects", json={
        "name": "Projeto de exemplo", "description": "Primeiro projeto"
    })
    assert created.status_code == 201
    payload = created.json()
    assert payload["name"] == "Projeto de exemplo"
    assert payload["status"] == "registered"
    assert payload["root_path"] is None
    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == payload["id"]

def test_project_name_cannot_be_blank(client):
    response = client.post("/api/v1/projects", json={"name": "   "})
    assert response.status_code == 422

def test_get_missing_project_returns_404(client):
    response = client.get("/api/v1/projects/999")
    assert response.status_code == 404

def test_update_project(client):
    created = client.post("/api/v1/projects", json={"name": "Nome inicial"})
    project_id = created.json()["id"]
    updated = client.patch(f"/api/v1/projects/{project_id}", json={
        "name": "Nome atualizado", "description": "Descrição nova"
    })
    assert updated.status_code == 200
    assert updated.json()["name"] == "Nome atualizado"
    assert updated.json()["description"] == "Descrição nova"

def test_import_analyze_and_list_project_history(client):
    archive = make_zip({
        "aplicativo/main.py": "print('olá')\n",
        "aplicativo/requirements.txt": "fastapi==0.115.12\n",
        "aplicativo/frontend/index.html": "<h1>Olá</h1>",
        "aplicativo/.env": "CHAVE=nao-importar",
        "aplicativo/node_modules/dependencia/index.js": "nao importar",
    })
    imported = client.post(
        "/api/v1/projects/import",
        data={"name": "Aplicativo", "description": "Projeto de teste"},
        files={"archive": ("aplicativo.zip", archive, "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    project = imported.json()
    assert project["status"] == "imported"
    assert project["root_path"]

    analysis_response = client.post(f"/api/v1/projects/{project['id']}/analyze")
    assert analysis_response.status_code == 200, analysis_response.text
    analysis = analysis_response.json()
    assert analysis["total_files"] == 3
    assert "Python" in analysis["detected_technologies"]
    assert any(path.endswith("main.py") for path in analysis["entrypoints"])
    assert analysis["files_omitted_from_list"] == 0

    saved_analysis = client.get(f"/api/v1/projects/{project['id']}/analysis")
    assert saved_analysis.status_code == 200
    assert saved_analysis.json()["total_files"] == 3

    history = client.get(f"/api/v1/projects/{project['id']}/events")
    assert history.status_code == 200
    assert [event["event_type"] for event in history.json()] == [
        "project_analyzed", "project_imported"
    ]

def test_import_rejects_zip_path_traversal(client):
    archive = make_zip({"../fora-do-projeto.txt": "conteúdo"})
    response = client.post(
        "/api/v1/projects/import",
        data={"name": "ZIP malicioso"},
        files={"archive": ("malicioso.zip", archive, "application/zip")},
    )
    assert response.status_code == 422
    assert "caminho" in response.json()["detail"]

def test_import_skips_dependency_and_secret_files(client):
    archive = make_zip({
        "src/main.py": "print('ok')",
        ".env": "TOKEN=segredo",
        ".env.development": "TOKEN=segredo",
        "node_modules/lib/index.js": "codigo",
    })
    response = client.post(
        "/api/v1/projects/import",
        data={"name": "Projeto limpo"},
        files={"archive": ("limpo.zip", archive, "application/zip")},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]
    analysis = client.post(f"/api/v1/projects/{project_id}/analyze").json()
    assert analysis["total_files"] == 1
    assert all(".env" not in path for path in analysis["files"])
    assert all("node_modules" not in path for path in analysis["files"])

def test_analysis_requires_an_imported_project(client):
    created = client.post("/api/v1/projects", json={"name": "Sem arquivos"})
    response = client.post(f"/api/v1/projects/{created.json()['id']}/analyze")
    assert response.status_code == 409

def test_analysis_of_unknown_project_returns_404(client):
    response = client.post("/api/v1/projects/404/analyze")
    assert response.status_code == 404


def test_project_memory_and_rescue_endpoints(client):
    archive = make_zip({"src/main.py": "print('ok')\n", "requirements.txt": ""})
    imported = client.post("/api/v1/projects/import", data={"name":"Memória e resgate"},
                           files={"archive":("projeto.zip",archive,"application/zip")})
    project_id = imported.json()["id"]
    client.post(f"/api/v1/projects/{project_id}/analyze")
    memory = client.get(f"/api/v1/projects/{project_id}/memory")
    assert memory.status_code == 200
    assert any(item["memory_key"] == "project_profile" for item in memory.json())
    saved = client.put(f"/api/v1/projects/{project_id}/memory",
                       json={"memory_key":"architecture","content":"Backend em Python e FastAPI."})
    assert saved.status_code == 200 and saved.json()["source"] == "user"
    report = client.post(f"/api/v1/projects/{project_id}/rescue")
    assert report.status_code == 200
    assert "findings" in report.json()
    runs = client.get(f"/api/v1/projects/{project_id}/runs")
    assert any(run["run_type"] == "rescue" for run in runs.json())


def test_authentication_isolates_project_accounts(client, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "s" * 48)
    first = client.post("/api/v1/auth/register", json={"email":"a@example.com","password":"senha-super-segura-123"})
    second = client.post("/api/v1/auth/register", json={"email":"b@example.com","password":"senha-super-segura-456"})
    assert first.status_code == 201 and second.status_code == 201
    token_a = first.json()["access_token"]
    token_b = second.json()["access_token"]
    created = client.post("/api/v1/projects", headers={"Authorization":f"Bearer {token_a}"},
                          json={"name":"Projeto privado"})
    project_id = created.json()["id"]
    hidden = client.get(f"/api/v1/projects/{project_id}", headers={"Authorization":f"Bearer {token_b}"})
    assert hidden.status_code == 404
    own = client.get(f"/api/v1/projects/{project_id}", headers={"Authorization":f"Bearer {token_a}"})
    assert own.status_code == 200


def test_authentication_requires_token_when_enabled(client, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "z" * 48)
    response = client.get("/api/v1/projects")
    assert response.status_code == 401

def test_sandbox_validation_is_logged(client, monkeypatch):
    import app.api.routes as routes
    archive = make_zip({"test_example.py":"def test_ok(): assert 1 + 1 == 2"})
    imported = client.post("/api/v1/projects/import", data={"name":"Validação"},
                           files={"archive":("tests.zip",archive,"application/zip")})
    project_id = imported.json()["id"]
    monkeypatch.setattr(routes, "run_python_tests", lambda root: {
        "status":"passed", "exit_code":0, "output":"1 passed", "sandbox":"Docker isolado"
    })
    result = client.post(f"/api/v1/projects/{project_id}/validate")
    assert result.status_code == 200
    runs = client.get(f"/api/v1/projects/{project_id}/runs").json()
    assert any(run["run_type"] == "pytest" and run["status"] == "passed" for run in runs)


def test_project_storage_path_cannot_be_supplied_or_changed(client):
    created = client.post("/api/v1/projects", json={"name":"Caminho protegido","root_path":"../fora"})
    assert created.status_code == 422
    valid = client.post("/api/v1/projects", json={"name":"Caminho interno"})
    project_id = valid.json()["id"]
    changed = client.patch(f"/api/v1/projects/{project_id}", json={"root_path":"../outro"})
    assert changed.status_code == 422


def test_failed_tests_create_repair_plan_for_approval(client, monkeypatch):
    import app.api.routes as routes
    from app.schemas.agent import AgentPlan
    archive = make_zip({"main.py":"def run(): return 1"})
    imported = client.post("/api/v1/projects/import", data={"name":"Projeto com falha"},
                           files={"archive":("falha.zip",archive,"application/zip")})
    project_id = imported.json()["id"]
    monkeypatch.setattr(routes, "run_python_tests", lambda root: {
        "status":"failed", "exit_code":1, "output":"AssertionError: esperado 2, recebido 1", "sandbox":"fake para teste"
    })
    monkeypatch.setattr(routes, "create_plan", lambda root, instruction, memory: AgentPlan(
        summary="Corrigir retorno", steps=[{"title":"Ajustar função","description":"Corrigir valor"}],
        proposed_changes=[{"path":"main.py","content":"def run(): return 2","reason":"Corrige teste"}], risks=[]
    ))
    response = client.post(f"/api/v1/projects/{project_id}/repair")
    assert response.status_code == 200
    assert response.json()["validation"]["status"] == "failed"
    assert response.json()["task"]["status"] == "awaiting_approval"
    assert response.json()["task"]["plan"]["proposed_changes"][0]["path"] == "main.py"


def test_account_overview_reports_plan_and_usage(client, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "m" * 48)
    registered = client.post("/api/v1/auth/register", json={
        "email": "uso@example.com", "password": "senha-super-segura-789"
    })
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    created = client.post("/api/v1/projects", headers=headers, json={"name": "Projeto 1"})
    assert created.status_code == 201
    overview = client.get("/api/v1/auth/me", headers=headers)
    assert overview.status_code == 200
    data = overview.json()
    assert data["email"] == "uso@example.com"
    assert data["plan"] == "free"
    assert data["projects_used"] == 1
    assert data["projects_limit"] == 3
    assert data["tasks_used_today"] == 0
    assert data["tasks_limit"] == 10


def test_account_overview_requires_authentication(client, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_agent_plan_requires_approval_before_applying_changes(client, monkeypatch):
    import app.api.routes as routes
    from app.schemas.agent import AgentPlan
    archive = make_zip({"src/main.py": "value = 1\n"})
    imported = client.post("/api/v1/projects/import", data={"name": "Fluxo do agente"},
                           files={"archive": ("agente.zip", archive, "application/zip")})
    assert imported.status_code == 201
    project = imported.json()
    project_root = routes.WORKSPACE_DIR / project["root_path"]
    target = project_root / "src" / "main.py"

    monkeypatch.setattr(routes, "create_plan", lambda root, instruction, memory: AgentPlan(
        summary="Atualizar valor", steps=[{"title": "Editar", "description": "Atualizar o valor inicial"}],
        proposed_changes=[{"path": "src/main.py", "content": "value = 2\n", "reason": "Atende à solicitação"}],
        risks=[]
    ))
    planned = client.post(f"/api/v1/projects/{project['id']}/tasks",
                          json={"instruction": "Atualize o valor inicial do módulo"})
    assert planned.status_code == 201, planned.text
    task = planned.json()
    assert task["status"] == "awaiting_approval"
    assert target.read_text(encoding="utf-8") == "value = 1\n"

    applied = client.post(f"/api/v1/tasks/{task['id']}/approve")
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "applied"
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    runs = client.get(f"/api/v1/projects/{project['id']}/runs").json()
    assert any(run["run_type"] == "planning" for run in runs)
    assert any(run["run_type"] == "apply" for run in runs)


def test_rejected_agent_plan_does_not_change_project_files(client, monkeypatch):
    import app.api.routes as routes
    from app.schemas.agent import AgentPlan
    archive = make_zip({"main.py": "value = 1\n"})
    imported = client.post("/api/v1/projects/import", data={"name": "Plano rejeitado"},
                           files={"archive": ("rejeitado.zip", archive, "application/zip")})
    project = imported.json()
    target = routes.WORKSPACE_DIR / project["root_path"] / "main.py"
    monkeypatch.setattr(routes, "create_plan", lambda root, instruction, memory: AgentPlan(
        summary="Alterar valor", steps=[], proposed_changes=[
            {"path": "main.py", "content": "value = 99\n", "reason": "Proposta"}
        ], risks=[]
    ))
    planned = client.post(f"/api/v1/projects/{project['id']}/tasks",
                          json={"instruction": "Altere o valor deste arquivo"})
    task_id = planned.json()["id"]
    rejected = client.post(f"/api/v1/tasks/{task_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_timeout_does_not_trigger_automatic_repair_proposal(client, monkeypatch):
    import app.api.routes as routes
    archive = make_zip({"main.py": "print('ok')"})
    imported = client.post("/api/v1/projects/import", data={"name": "Teste expirado"},
                           files={"archive": ("timeout.zip", archive, "application/zip")})
    project_id = imported.json()["id"]
    monkeypatch.setattr(routes, "run_python_tests", lambda root: {
        "status": "timeout", "exit_code": None, "output": "Tempo limite excedido",
        "sandbox": "sandbox de teste"
    })
    monkeypatch.setattr(routes, "create_plan", lambda *args: (_ for _ in ()).throw(
        AssertionError("A IA não deve propor reparos para timeout")
    ))
    response = client.post(f"/api/v1/projects/{project_id}/repair")
    assert response.status_code == 200
    assert response.json()["validation"]["status"] == "timeout"
    assert response.json()["task"] is None
    assert "não produziu uma falha" in response.json()["planning_error"]


def test_repair_plan_consumes_ai_quota(client, monkeypatch):
    import app.api.routes as routes
    from app.schemas.agent import AgentPlan
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "r" * 48)
    registered = client.post("/api/v1/auth/register", json={
        "email": "reparo@example.com", "password": "senha-super-segura-321"
    })
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    archive = make_zip({"main.py": "value = 1"})
    imported = client.post("/api/v1/projects/import", headers=headers, data={"name": "Cota de reparo"},
                           files={"archive": ("reparo.zip", archive, "application/zip")})
    project_id = imported.json()["id"]
    monkeypatch.setattr(routes, "run_python_tests", lambda root: {
        "status": "failed", "exit_code": 1, "output": "AssertionError",
        "sandbox": "sandbox de teste"
    })
    monkeypatch.setattr(routes, "create_plan", lambda *args: AgentPlan(
        summary="Analisar falha", steps=[], proposed_changes=[], risks=[]
    ))
    response = client.post(f"/api/v1/projects/{project_id}/repair", headers=headers)
    assert response.status_code == 200
    usage = client.get("/api/v1/auth/me", headers=headers).json()
    assert usage["tasks_used_today"] == 1


def test_repair_respects_daily_ai_quota(client, monkeypatch):
    import app.api.routes as routes
    from app.schemas.agent import AgentPlan
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "q" * 48)
    registered = client.post("/api/v1/auth/register", json={
        "email": "limite@example.com", "password": "senha-super-segura-654"
    })
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    archive = make_zip({"main.py": "value = 1"})
    imported = client.post("/api/v1/projects/import", headers=headers, data={"name": "Limite IA"},
                           files={"archive": ("limite.zip", archive, "application/zip")})
    project_id = imported.json()["id"]
    monkeypatch.setattr(routes, "create_plan", lambda *args: AgentPlan(
        summary="Plano sem alterações", steps=[], proposed_changes=[], risks=[]
    ))
    for index in range(10):
        task = client.post(f"/api/v1/projects/{project_id}/tasks", headers=headers,
                           json={"instruction": f"Analise a tarefa de teste número {index}"})
        assert task.status_code == 201
    monkeypatch.setattr(routes, "run_python_tests", lambda root: {
        "status": "failed", "exit_code": 1, "output": "AssertionError",
        "sandbox": "sandbox de teste"
    })
    blocked = client.post(f"/api/v1/projects/{project_id}/repair", headers=headers)
    assert blocked.status_code == 429


def test_free_plan_project_limit_is_enforced(client, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "AUTH_REQUIRED", True)
    monkeypatch.setenv("DEVPILOT_AUTH_SECRET", "p" * 48)
    registered = client.post("/api/v1/auth/register", json={
        "email": "projetos@example.com", "password": "senha-super-segura-987"
    })
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    for index in range(3):
        response = client.post("/api/v1/projects", headers=headers,
                               json={"name": f"Projeto gratuito {index + 1}"})
        assert response.status_code == 201
    blocked = client.post("/api/v1/projects", headers=headers,
                          json={"name": "Projeto além da cota"})
    assert blocked.status_code == 429
