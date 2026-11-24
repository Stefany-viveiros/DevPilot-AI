import io
import subprocess
from unittest.mock import patch

from app.services.sandbox import MAX_OUTPUT, _read_bounded_output, run_python_tests


class FakeProcess:
    def __init__(self, output=b"2 passed"):
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


def test_sandbox_timeout_is_reported(tmp_path):
    process = FakeProcess(b"still running")
    process.timeout = True
    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.Popen", return_value=process
    ):
        result = run_python_tests(tmp_path)
    assert result["status"] == "timeout"
    assert process.killed


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
