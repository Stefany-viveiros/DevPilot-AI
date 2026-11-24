import pytest
from app.schemas.agent import AgentPlan
from app.services.agent import apply_plan, validate_path

def test_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError): validate_path(tmp_path, "../outside.txt")

def test_rejects_sensitive_file(tmp_path):
    with pytest.raises(ValueError): validate_path(tmp_path, ".env")

def test_rejects_symlink(tmp_path):
    outside = tmp_path.parent / "outside"; outside.mkdir()
    try: (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError): pytest.skip("Symlink indisponível")
    with pytest.raises(ValueError): validate_path(tmp_path, "link/file.py")

def test_apply_writes_only_when_called(tmp_path):
    plan = AgentPlan.model_validate({"summary":"Criar", "steps":[], "proposed_changes":[{"path":"src/main.py","content":"print('oi')","reason":"teste"}], "risks":[]})
    assert not (tmp_path / "src/main.py").exists()
    assert apply_plan(tmp_path, plan) == ["src/main.py"]
    assert (tmp_path / "src/main.py").read_text() == "print('oi')"

def test_empty_plan_cannot_be_applied(tmp_path):
    plan = AgentPlan.model_validate({"summary":"Sem mudanças", "steps":[], "proposed_changes":[], "risks":[]})
    with pytest.raises(ValueError): apply_plan(tmp_path, plan)
