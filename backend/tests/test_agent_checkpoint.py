import json
import zipfile

import pytest

from app.schemas.agent import AgentPlan
from app.services.agent import create_checkpoint, restore_checkpoint


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


def test_restore_checkpoint_reverts_existing_file_and_removes_new_file(tmp_path):
    project = tmp_path / "projeto"
    project.mkdir()
    original = project / "app.py"
    original.write_text("versão original", encoding="utf-8")
    destination = tmp_path / "backups" / "task-4.zip"
    plan = make_plan("app.py", "novo.py")
    create_checkpoint(project, plan, destination)

    original.write_text("versão modificada", encoding="utf-8")
    (project / "novo.py").write_text("arquivo criado pela tarefa", encoding="utf-8")
    restored = restore_checkpoint(project, destination)

    assert set(restored) == {"app.py", "novo.py"}
    assert original.read_text(encoding="utf-8") == "versão original"
    assert not (project / "novo.py").exists()


def test_restore_rejects_corrupt_checkpoint_without_changing_project(tmp_path):
    project = tmp_path / "projeto"
    project.mkdir()
    target = project / "app.py"
    target.write_text("não alterar", encoding="utf-8")
    destination = tmp_path / "corrupt.zip"
    destination.write_text("arquivo inválido", encoding="utf-8")

    with pytest.raises(zipfile.BadZipFile):
        restore_checkpoint(project, destination)

    assert target.read_text(encoding="utf-8") == "não alterar"


def test_restore_rejects_path_traversal_in_checkpoint_manifest(tmp_path):
    project = tmp_path / "projeto"
    project.mkdir()
    outside = tmp_path / "fora.txt"
    outside.write_text("conteúdo protegido", encoding="utf-8")
    destination = tmp_path / "malicioso.zip"
    manifest = {"files": [{"path": "../fora.txt", "existed": False}]}
    with zipfile.ZipFile(destination, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))

    with pytest.raises(ValueError):
        restore_checkpoint(project, destination)

    assert outside.read_text(encoding="utf-8") == "conteúdo protegido"
