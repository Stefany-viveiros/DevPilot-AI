from unittest.mock import patch
from app.services.sandbox import run_python_tests

def test_sandbox_invocation_is_restricted(tmp_path):
    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.run"
    ) as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "2 passed"
        run.return_value.stderr = ""
        result = run_python_tests(tmp_path)
    command = run.call_args.args[0]
    assert "--network" in command and "none" in command
    assert "--read-only" in command
    assert "--cap-drop" in command and "ALL" in command
    assert result["status"] == "passed"

def test_sandbox_timeout_is_reported(tmp_path):
    import subprocess
    with patch("app.services.sandbox.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.services.sandbox.subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 120)
    ):
        assert run_python_tests(tmp_path)["status"] == "timeout"
