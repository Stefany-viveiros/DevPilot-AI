import json
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from app.schemas.agent import AgentPlan

BLOCKED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".env", ".env.local", ".env.production"}
SENSITIVE = ("secret", "token", "password", "credential", "id_rsa")

class AgentProviderError(RuntimeError):
    pass

def _context(root: Path) -> str:
    chunks, size = [], 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(p.lower() in BLOCKED for p in rel.parts) or any(s in path.name.lower() for s in SENSITIVE):
            continue
        if path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".md", ".toml", ".yml", ".yaml", ".sql"}:
            continue
        try:
            data = path.read_bytes()
            if len(data) > 12000 or b"\0" in data:
                continue
            chunk = f"\n--- {rel.as_posix()} ---\n{data.decode('utf-8')}"
        except (OSError, UnicodeDecodeError):
            continue
        if size + len(chunk.encode()) > 80000:
            break
        chunks.append(chunk); size += len(chunk.encode())
    return "".join(chunks) or "(Sem arquivos textuais seguros.)"

def validate_path(root: Path, raw: str) -> Path:
    normalized = raw.replace("\\", "/")
    rel = PurePosixPath(normalized)
    if not normalized or rel.is_absolute() or any(p in {"", ".", ".."} for p in rel.parts):
        raise ValueError("Caminho relativo inválido.")
    if any(p.lower() in BLOCKED for p in rel.parts) or any(s in rel.name.lower() for s in SENSITIVE):
        raise ValueError("Caminho protegido ou potencialmente sensível.")
    target = root.joinpath(*rel.parts)
    if not target.resolve(strict=False).is_relative_to(root.resolve()):
        raise ValueError("Caminho fora da pasta autorizada.")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Links simbólicos não são permitidos.")
    return target

def create_plan(root: Path, instruction: str) -> AgentPlan:
    base = __import__("os").getenv("DEVPILOT_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    model = __import__("os").getenv("DEVPILOT_OLLAMA_MODEL", "qwen2.5-coder:3b")
    prompt = f"""Planeje a solicitação para este projeto. Retorne SOMENTE JSON válido com summary, steps (array de {{"title","description"}}), proposed_changes (array de {{"path","content","reason"}}) e risks (array).
Cada content deve ser o arquivo completo. Use caminhos relativos, no máximo 20 arquivos e 200KB por conteúdo. Não altere arquivos/pastas sensíveis, .git ou dependências. Se não souber, não proponha alterações e explique o risco.
SOLICITAÇÃO: {instruction}
CONTEXTO:{_context(root)}"""
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}, ensure_ascii=False).encode()
    req = urllib.request.Request(base + "/api/generate", data=body, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = json.loads(response.read().decode()).get("response", "")
        plan = AgentPlan.model_validate(json.loads(raw))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AgentProviderError("Ollama indisponível. Inicie o Ollama e baixe o modelo configurado.") from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise AgentProviderError("A IA retornou um plano inválido. Reformule a solicitação.") from exc
    if len(plan.proposed_changes) > 20:
        raise AgentProviderError("O plano excede o limite de 20 arquivos.")
    for change in plan.proposed_changes:
        if not {"path", "content"}.issubset(change) or len(change["content"].encode()) > 200000:
            raise AgentProviderError("Uma alteração não atende ao formato ou limite de tamanho.")
        validate_path(root, change["path"])
    return plan

def apply_plan(root: Path, plan: AgentPlan) -> list[str]:
    if not plan.proposed_changes:
        raise ValueError("O plano não contém alterações aplicáveis.")
    targets = [(validate_path(root, item["path"]), item) for item in plan.proposed_changes]
    backups, written = {}, []
    try:
        for target, item in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            backups[target] = target.read_bytes() if target.exists() else None
            temp = target.with_name(target.name + ".devpilot-tmp")
            temp.write_text(item["content"], encoding="utf-8")
            temp.replace(target); written.append(target)
    except Exception:
        for target in reversed(written):
            old = backups[target]
            if old is None: target.unlink(missing_ok=True)
            else: target.write_bytes(old)
        raise
    return [p.relative_to(root).as_posix() for p, _ in targets]
