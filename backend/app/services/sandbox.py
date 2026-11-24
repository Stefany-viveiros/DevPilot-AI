import shutil
import subprocess
from pathlib import Path

SANDBOX_IMAGE = "devpilot-sandbox:py311"
MAX_OUTPUT = 12000
TIMEOUT_SECONDS = 120

class SandboxUnavailable(RuntimeError):
    pass

def run_python_tests(project_root: Path) -> dict:
    docker = shutil.which("docker")
    if not docker:
        raise SandboxUnavailable("Docker não foi encontrado. Instale e inicie o Docker Desktop para validar projetos em sandbox.")
    if not project_root.is_dir() or project_root.is_symlink():
        raise SandboxUnavailable("A pasta do projeto não é válida para execução isolada.")
    command = [
        docker, "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--mount", f"type=bind,src={project_root.resolve()},dst=/workspace,readonly",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "TMPDIR=/tmp",
        "--workdir", "/workspace", SANDBOX_IMAGE, "python", "-m", "pytest", "-p", "no:cacheprovider", "-q",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "exit_code": None, "output": "Tempo limite de 120 segundos excedido.", "sandbox": "Docker sem rede, raiz somente leitura e limites de recursos."}
    except OSError as exc:
        raise SandboxUnavailable("Não foi possível iniciar o Docker.") from exc
    output = (completed.stdout + "\n" + completed.stderr).strip()
    if "Unable to find image" in output or "pull access denied" in output:
        raise SandboxUnavailable(f"Imagem {SANDBOX_IMAGE} ausente. Construa-a com: docker build -t {SANDBOX_IMAGE} sandbox/")
    return {"status": "passed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode, "output": output[-MAX_OUTPUT:],
            "sandbox": "Docker sem rede, raiz somente leitura, sem capabilities e com limites de CPU/memória/processos."}
