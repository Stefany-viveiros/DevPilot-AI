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
    assert "main.py" in analysis["entrypoints"][0]
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
