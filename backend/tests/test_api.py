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
