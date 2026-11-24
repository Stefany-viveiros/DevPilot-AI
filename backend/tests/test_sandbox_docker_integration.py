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
    source.write_text("throw new Error('Este código não deve ser executado');", encoding="utf-8")
    valid = run_python_tests(tmp_path)
    assert valid["status"] == "passed", valid["output"]
    checks = {item["name"]: item for item in valid["checks"]}
    assert checks["javascript_syntax"]["status"] == "passed"
    assert checks["javascript_syntax"]["files_checked"] == 1

    source.write_text("const = ;", encoding="utf-8")
    invalid = run_python_tests(tmp_path)
    assert invalid["status"] == "failed"
    assert "SyntaxError" in invalid["output"]
    source.unlink()

    tsx = tmp_path / "component.tsx"
    tsx.write_text(
        "type Props = { label: string }; export function Button(props: Props) { return <button>{props.label}</button>; }",
        encoding="utf-8",
    )
    valid_tsx = run_python_tests(tmp_path)
    assert valid_tsx["status"] == "passed", valid_tsx["output"]
    ts_checks = {item["name"]: item for item in valid_tsx["checks"]}
    assert ts_checks["typescript_syntax"]["status"] == "passed"
    assert ts_checks["typescript_syntax"]["files_checked"] == 1

    tsx.write_text("const value: = 3;", encoding="utf-8")
    invalid_tsx = run_python_tests(tmp_path)
    assert invalid_tsx["status"] == "failed"
    assert "TypeScript/JSX" in invalid_tsx["output"]
