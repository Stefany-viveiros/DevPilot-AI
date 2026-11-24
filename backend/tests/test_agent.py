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


@pytest.mark.parametrize("path", [".env.development", "config/private_key.json", "certificados/chave.pem"])
def test_rejects_sensitive_paths(tmp_path, path):
    with pytest.raises(ValueError):
        validate_path(tmp_path, path)


def test_apply_refuses_to_backup_oversized_existing_file(tmp_path):
    target = tmp_path / "large.py"
    target.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    plan = AgentPlan.model_validate({
        "summary": "Alterar arquivo grande", "steps": [],
        "proposed_changes": [{"path": "large.py", "content": "novo", "reason": "teste"}],
        "risks": [],
    })
    with pytest.raises(ValueError, match="10 MB"):
        apply_plan(tmp_path, plan)
    assert target.stat().st_size == 10 * 1024 * 1024 + 1


def test_rejects_oversized_model_response(tmp_path, monkeypatch):
    from unittest.mock import patch
    from app.services.agent import AgentProviderError, MAX_PLAN_RESPONSE_BYTES, create_plan

    class LargeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return b"x" * size

    with patch("app.services.agent.urllib.request.urlopen", return_value=LargeResponse()):
        with pytest.raises(AgentProviderError, match="1 MB"):
            create_plan(tmp_path, "Analise o projeto e proponha melhorias")


def test_apply_rejects_duplicate_file_paths(tmp_path):
    plan = AgentPlan.model_validate({
        "summary": "Alterar duas vezes", "steps": [],
        "proposed_changes": [
            {"path": "main.py", "content": "primeiro", "reason": "a"},
            {"path": "main.py", "content": "segundo", "reason": "b"},
        ],
        "risks": [],
    })
    with pytest.raises(ValueError, match="duplicados"):
        apply_plan(tmp_path, plan)
    assert not (tmp_path / "main.py").exists()


def test_apply_does_not_follow_precreated_temporary_symlink(tmp_path):
    outside = tmp_path.parent / "outside-target.txt"
    outside.write_text("conteudo original", encoding="utf-8")
    temporary_link = tmp_path / "main.py.devpilot-tmp"
    try:
        temporary_link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink indisponível neste ambiente")
    plan = AgentPlan.model_validate({
        "summary": "Criar arquivo", "steps": [],
        "proposed_changes": [{"path": "main.py", "content": "conteudo seguro", "reason": "teste"}],
        "risks": [],
    })
    apply_plan(tmp_path, plan)
    assert outside.read_text(encoding="utf-8") == "conteudo original"
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == "conteudo seguro"


def test_new_agent_files_are_readable_by_sandbox_user(tmp_path):
    import os
    import stat
    plan = AgentPlan.model_validate({
        "summary": "Criar módulo", "steps": [],
        "proposed_changes": [{"path": "generated.py", "content": "value = 1\n", "reason": "teste"}],
        "risks": [],
    })
    apply_plan(tmp_path, plan)
    if os.name != "nt":
        assert stat.S_IMODE((tmp_path / "generated.py").stat().st_mode) == 0o644
