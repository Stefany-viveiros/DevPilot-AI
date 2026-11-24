import json
import zipfile

import pytest

from app.schemas.agent import AgentPlan
from app.services.agent import create_checkpoint


def make_plan(*paths):
    return AgentPlan(
        summary="Atualizar arquivos",
        steps=[{"title": "Atualizar", "description": "Aplicar mudança"}],
        proposed_changes=[{"path": path, "content": "novo conteúdo", "reason": "teste"} for path in paths],
        risks=[],
    )


def test_checkpoint_preserves_existing_files_and_records_new_files(tmp_path):
    project = tmp_path / "projeto"
    project.mkdir()
    (project / "app.py").write_text("conteúdo antigo", encoding="utf-8")
    destination = tmp_path / "backups" / "task-1.zip"

    result = create_checkpoint(project, make_plan("app.py", "novo.py"), destination)

    assert destination.is_file()
    assert result["files"] == 2
    assert result["backed_up_files"] == 1
    with zipfile.ZipFile(destination) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert archive.read("files/app.py").decode("utf-8") == "conteúdo antigo"
    assert manifest["files"][1]["existed"] is False


def test_checkpoint_rejects_oversized_existing_file(tmp_path):
    project = tmp_path / "projeto"
    project.mkdir()
    (project / "large.py").write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    destination = tmp_path / "backups" / "task-2.zip"

    with pytest.raises(ValueError, match="10 MB"):
        create_checkpoint(project, make_plan("large.py"), destination)

    assert not destination.exists()


def test_checkpoint_rejects_symlink_target(tmp_path):
    project = tmp_path / "projeto"
    project.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("não tocar", encoding="utf-8")
    (project / "linked.py").symlink_to(outside)
    destination = tmp_path / "backups" / "task-3.zip"

    with pytest.raises(ValueError):
        create_checkpoint(project, make_plan("linked.py"), destination)

    assert not destination.exists()
