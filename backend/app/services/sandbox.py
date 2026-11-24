import os
import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path
from threading import Thread

SANDBOX_IMAGE = "devpilot-sandbox:py311"
MAX_OUTPUT = 12000
TIMEOUT_SECONDS = 120
READ_CHUNK = 4096


class SandboxUnavailable(RuntimeError):
    pass


def _read_bounded_output(stream, limit: int = MAX_OUTPUT) -> str:
    """Drena a saída inteira sem manter mais que 'limit' bytes em memória."""
    chunks: deque[bytes] = deque()
    size = 0
    while True:
        chunk = stream.read(READ_CHUNK)
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
        while size > limit and chunks:
            excess = size - limit
            first = chunks[0]
            if len(first) <= excess:
                size -= len(chunks.popleft())
            else:
                chunks[0] = first[excess:]
                size -= excess
    return b"".join(chunks).decode("utf-8", errors="replace")


def run_python_tests(project_root: Path) -> dict:
    docker = shutil.which("docker")
    if not docker:
        raise SandboxUnavailable("Docker não foi encontrado. Instale e inicie o Docker Desktop para validar projetos em sandbox.")
    if not project_root.is_dir() or project_root.is_symlink():
        raise SandboxUnavailable("A pasta do projeto não é válida para execução isolada.")
    cid_file = tempfile.NamedTemporaryFile(prefix="devpilot-", suffix=".cid", delete=False)
    cid_path = cid_file.name
    cid_file.close()
    os.unlink(cid_path)
    command = [
        docker, "run", "--cidfile", cid_path, "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "--mount", f"type=bind,src={project_root.resolve()},dst=/workspace,readonly",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "TMPDIR=/tmp",
        "--workdir", "/workspace", SANDBOX_IMAGE, "python", "/opt/devpilot/validate.py",
    ]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as exc:
        Path(cid_path).unlink(missing_ok=True)
        raise SandboxUnavailable("Não foi possível iniciar o Docker.") from exc

    output: dict[str, str] = {}
    reader = Thread(target=lambda: output.setdefault("text", _read_bounded_output(process.stdout)), daemon=True)
    reader.start()
    timed_out = False
    try:
        return_code = process.wait(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        return_code = process.wait()
        try:
            container_id = Path(cid_path).read_text(encoding="ascii").strip()
            if container_id and all(char in "0123456789abcdef" for char in container_id.lower()):
                stopped = subprocess.run(
                    [docker, "stop", "--time", "2", container_id],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5, check=False,
                )
                if stopped.returncode != 0:
                    subprocess.run(
                        [docker, "rm", "-f", container_id],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=5, check=False,
                    )
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
            pass
    finally:
        reader.join(timeout=5)
        if process.stdout:
            process.stdout.close()
        Path(cid_path).unlink(missing_ok=True)

    captured = output.get("text", "")[-MAX_OUTPUT:]
    sandbox_description = (
        "Docker sem rede, raiz e projeto somente leitura, sem capabilities, limites de CPU/memória/processos; "
        "análise sintática Python, pytest, node --check e análise sintática TypeScript/JSX; saída limitada a 12 KB."
    )
    if timed_out:
        return {"status": "timeout", "exit_code": None,
                "output": (captured + "\nTempo limite global de 120 segundos excedido.")[-MAX_OUTPUT:],
                "sandbox": sandbox_description, "checks": []}
    if "Unable to find image" in captured or "pull access denied" in captured:
        raise SandboxUnavailable(f"Imagem {SANDBOX_IMAGE} ausente. Construa-a com: docker build -t {SANDBOX_IMAGE} sandbox/")
    marker = "RESULTADO_JSON="
    if marker not in captured:
        raise SandboxUnavailable("O executor isolado não retornou um relatório válido. Reconstrua a imagem Docker.")
    report_text = captured.rsplit(marker, 1)[1].strip()
    try:
        import json
        report = json.loads(report_text)
    except (ValueError, TypeError) as exc:
        raise SandboxUnavailable("O relatório do executor isolado está inválido. Reconstrua a imagem Docker.") from exc
    status = report.get("status")
    if status not in {"passed", "failed", "inconclusive", "not_applicable"}:
        raise SandboxUnavailable("O executor isolado retornou um estado desconhecido.")
    output_text = captured.rsplit(marker, 1)[0].strip()
    return {
        "status": status,
        "exit_code": 0 if status in {"passed", "not_applicable"} else (1 if status == "failed" else None),
        "output": output_text[-MAX_OUTPUT:],
        "sandbox": sandbox_description,
        "checks": report.get("checks", []),
        "javascript_scan_incomplete": bool(report.get("javascript_scan_incomplete", False)),
    }
