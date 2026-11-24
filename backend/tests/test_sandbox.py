import io
import subprocess
from unittest.mock import patch

from app.services.sandbox import MAX_OUTPUT, _read_bounded_output, run_python_tests


class FakeProcess:
    def __init__(self, output=b'2 passed\nRESULTADO_JSON={"status":"passed","checks":[{"name":"pytest","status":"passed"}],"javascript_scan_incomplete":false}'):
        self.stdout = io.BytesIO(output)
        self.wait_calls = 0
        self.killed = False

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_calls == 1 and timeout is not None and self.timeout:
            raise subprocess.TimeoutExpired("docker", timeout)
        return -9 if self.killed else 0

    def kill(self):
        self.killed = True

    timeout = False


def test_sandbox_invocation_is_restricted(tmp_path):
    process = FakeProcess()
    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.Popen", return_value=process
    ) as popen:
        result = run_python_tests(tmp_path)
    command = popen.call_args.args[0]
    assert "--network" in command and "none" in command
    assert "--read-only" in command
    assert "--cap-drop" in command and "ALL" in command
    assert result["status"] == "passed"
    assert result["output"] == "2 passed"
    assert result["checks"][0]["name"] == "pytest"
    assert command[-1] == "/opt/devpilot/validate.py"


def test_sandbox_timeout_is_reported_and_container_is_stopped(tmp_path):
    from pathlib import Path
    process = FakeProcess(b"still running")
    process.timeout = True

    def start_container(command, **kwargs):
        cid_path = Path(command[command.index("--cidfile") + 1])
        cid_path.write_text("a" * 64, encoding="ascii")
        return process

    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.Popen", side_effect=start_container
    ), patch("app.services.sandbox.subprocess.run") as cleanup:
        cleanup.return_value.returncode = 0
        result = run_python_tests(tmp_path)
    assert result["status"] == "timeout"
    assert process.killed
    assert cleanup.call_args.args[0][:4] == ["/usr/bin/docker", "stop", "--time", "2"]
    assert cleanup.call_args.args[0][-1] == "a" * 64


def test_sandbox_output_is_bounded_to_last_bytes():
    output = _read_bounded_output(io.BytesIO(b"x" * (MAX_OUTPUT + 100)))
    assert len(output.encode()) == MAX_OUTPUT
    assert output == "x" * MAX_OUTPUT


def test_sandbox_rejects_symlinked_project_root(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.Popen"
    ) as popen:
        from app.services.sandbox import SandboxUnavailable
        import pytest
        with pytest.raises(SandboxUnavailable):
            run_python_tests(link)
        popen.assert_not_called()



def test_sandbox_reports_not_applicable_when_no_supported_checks_exist(tmp_path):
    report = b'RESULTADO_JSON={"status":"not_applicable","checks":[{"name":"pytest","status":"skipped"},{"name":"python_syntax","status":"skipped"},{"name":"javascript_syntax","status":"skipped"},{"name":"typescript_syntax","status":"skipped"}],"javascript_scan_incomplete":false}'
    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.Popen", return_value=FakeProcess(report)
    ):
        result = run_python_tests(tmp_path)
    assert result["status"] == "not_applicable"
    assert result["exit_code"] == 0
    assert len(result["checks"]) == 4


def test_sandbox_rejects_missing_structured_report(tmp_path):
    from app.services.sandbox import SandboxUnavailable
    import pytest

    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.Popen", return_value=FakeProcess("output sem relatório".encode("utf-8"))
    ):
        with pytest.raises(SandboxUnavailable, match="relatório válido"):
            run_python_tests(tmp_path)
