from pathlib import Path
from app.services.project_analysis import analyze_project

def rescue_project(root: Path) -> dict:
    analysis = analyze_project(root)
    files = set(analysis["files"])
    findings = []
    def add(severity, title, detail, recommendation):
        findings.append({"severity": severity, "title": title, "detail": detail, "recommendation": recommendation})
    if not any(name.lower().startswith("readme") for name in files):
        add("medium", "Documentação ausente", "Não foi encontrado README na raiz ou nos arquivos listados.", "Crie um README com instalação, execução e configuração.")
    if not any("test" in Path(name).parts or Path(name).name.lower().startswith(("test_", "test.")) for name in files):
        add("high", "Testes não identificados", "Nenhum arquivo de teste foi reconhecido pela análise estrutural.", "Adicione testes automatizados para os fluxos críticos.")
    if not any(Path(name).name.lower() in {"pyproject.toml", "requirements.txt", "package.json", "pom.xml", "cargo.toml", "go.mod"} for name in files):
        add("medium", "Manifesto de dependências ausente", "Não foi encontrado um manifesto conhecido.", "Documente e fixe as dependências do projeto.")
    todo_files = []
    for rel in sorted(files):
        path = root / rel
        if path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "TODO" in text or "FIXME" in text or "NotImplementedError" in text:
            todo_files.append(rel)
    if todo_files:
        add("low", "Pendências no código", f"Foram encontrados marcadores em {len(todo_files)} arquivo(s): " + ", ".join(todo_files[:10]), "Revise as pendências e transforme-as em tarefas priorizadas.")
    if analysis["total_files"] == 0:
        add("high", "Projeto vazio ou sem arquivos reconhecíveis", "A pasta importada não contém arquivos analisáveis.", "Verifique o ZIP e importe novamente a pasta correta.")
    score = max(0, 100 - sum({"high": 25, "medium": 12, "low": 4}[f["severity"]] for f in findings))
    return {"score": score, "total_findings": len(findings), "findings": findings,
            "project_summary": {"total_files": analysis["total_files"], "technologies": analysis["detected_technologies"], "entrypoints": analysis["entrypoints"]},
            "limitations": ["Diagnóstico estático: não executa código nem comprova a presença de defeitos.", "A pontuação é indicativa e não substitui revisão técnica."]}
