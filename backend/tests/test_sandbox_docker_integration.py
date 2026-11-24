import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.sandbox import SANDBOX_IMAGE, run_python_tests


@pytest.mark.skipif(not shutil.which("docker"), reason="Docker não está instalado.")
def test_real_docker_sandbox_runs_tests_with_read_only_project(tmp_path):
    image = subprocess.run(
        ["docker", "image", "inspect", SANDBOX_IMAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if image.returncode != 0:
        pytest.skip("Imagem de sandbox ainda não foi construída.")

    # O contêiner usa UID sem privilégios; a pasta montada precisa ser atravessável.
    tmp_path.chmod(0o755)
    (tmp_path / "test_example.py").write_text(
        "from pathlib import Path\n"
        "def test_project_is_read_only():\n"
        "    try:\n"
        "        Path(__file__).write_text('alterado')\n"
        "    except OSError:\n"
        "        return\n"
        "    raise AssertionError('O projeto deveria estar montado como somente leitura')\n",
        encoding="utf-8",
    )
    result = run_python_tests(tmp_path)
    assert result["status"] == "passed", result["output"]
    assert "somente leitura" in result["sandbox"]



@pytest.mark.skipif(not shutil.which("docker"), reason="Docker não está instalado.")
def test_real_docker_sandbox_checks_javascript_syntax_without_executing_it(tmp_path):
    image = subprocess.run(
        ["docker", "image", "inspect", SANDBOX_IMAGE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if image.returncode != 0:
        pytest.skip("Imagem de sandbox ainda não foi construída.")

    tmp_path.chmod(0o755)
    source = tmp_path / "app.js"
    source.write_text(
        "require('fs').writeFileSync('/workspace/nao-deve-existir.txt', 'executado');",
        encoding="utf-8",
    )
    valid = run_python_tests(tmp_path)
    assert valid["status"] == "passed", valid["output"]
    checks = {item["name"]: item for item in valid["checks"]}
    assert checks["javascript_syntax"]["status"] == "passed"
    assert checks["javascript_syntax"]["files_checked"] == 1
    assert not (tmp_path / "nao-deve-existir.txt").exists()

    source.write_text("const = ;", encoding="utf-8")
    invalid = run_python_tests(tmp_path)
    assert invalid["status"] == "failed"
    assert "SyntaxError" in invalid["output"]
