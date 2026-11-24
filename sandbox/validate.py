import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path("/workspace")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "coverage"}
MAX_SOURCE_FILES = 100
MAX_SOURCE_FILE_BYTES = 1_000_000
MAX_SOURCE_TOTAL_BYTES = 20_000_000
MAX_CAPTURE_BYTES = 12_000
JS_SUFFIXES = {".js", ".mjs", ".cjs"}
TS_SUFFIXES = {".ts", ".tsx", ".mts", ".cts", ".jsx"}
TS_CHECK_SCRIPT = """
const fs = require('fs');
const ts = require('/usr/local/lib/node_modules/typescript');
const file = process.argv[1];
const source = fs.readFileSync(file, 'utf8');
const result = ts.transpileModule(source, {
  fileName: file,
  reportDiagnostics: true,
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    jsx: ts.JsxEmit.Preserve
  }
});
const errors = (result.diagnostics || []).filter(
  item => item.category === ts.DiagnosticCategory.Error
);
for (const item of errors) {
  console.error(file + ': ' + ts.flattenDiagnosticMessageText(item.messageText, '\\n'));
}
process.exitCode = errors.length ? 1 : 0;
"""


def tail(file_obj, limit=MAX_CAPTURE_BYTES):
    file_obj.flush()
    size = file_obj.seek(0, os.SEEK_END)
    file_obj.seek(max(0, size - limit))
    return file_obj.read().decode("utf-8", errors="replace")


def run_check(command, timeout):
    with tempfile.TemporaryFile(mode="w+b") as output:
        try:
            completed = subprocess.run(
                command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
            return completed.returncode, tail(output), False
        except subprocess.TimeoutExpired:
            return None, tail(output) + "\nTempo limite desta verificação excedido.", True


def discover_sources():
    found = {"javascript": [], "typescript": []}
    total_bytes = 0
    incomplete = False
    for current, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS
                   and not (Path(current) / name).is_symlink()]
        for name in files:
            path = Path(current) / name
            suffix = path.suffix.lower()
            if suffix in JS_SUFFIXES:
                group = "javascript"
            elif suffix in TS_SUFFIXES:
                group = "typescript"
            else:
                continue
            if path.is_symlink():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                incomplete = True
                continue
            if size > MAX_SOURCE_FILE_BYTES or total_bytes + size > MAX_SOURCE_TOTAL_BYTES:
                incomplete = True
                continue
            found[group].append(path)
            total_bytes += size
            if sum(len(items) for items in found.values()) > MAX_SOURCE_FILES:
                incomplete = True
                for key in found:
                    found[key] = found[key][:MAX_SOURCE_FILES]
                return found, incomplete
    return found, incomplete


def main():
    results = []
    output_parts = []
    python_tests = []
    for current, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS
                   and not (Path(current) / name).is_symlink()]
        if any(name.startswith("test_") and name.endswith(".py") for name in files) or any(
            name.endswith("_test.py") for name in files
        ):
            python_tests.append(Path(current))
    if python_tests:
        code, output, timed_out = run_check(
            ["python", "-m", "pytest", "-p", "no:cacheprovider", "-q"], 95
        )
        state = "timeout" if timed_out else ("passed" if code == 0 else "failed")
        results.append({"name": "pytest", "status": state, "exit_code": code})
        output_parts.append("=== Testes Python (pytest) ===\n" + output)
    else:
        results.append({"name": "pytest", "status": "skipped", "exit_code": None})
        output_parts.append("=== Testes Python (pytest) ===\nNenhum arquivo de teste Python foi encontrado.")

    sources, scan_incomplete = discover_sources()
    checks = (
        ("javascript_syntax", "JavaScript", sources["javascript"],
         lambda path: ["node", "--check", str(path)], 5, ".js/.mjs/.cjs"),
        ("typescript_syntax", "TypeScript/JSX", sources["typescript"],
         lambda path: ["node", "-e", TS_CHECK_SCRIPT, str(path)], 8, ".ts/.tsx/.mts/.cts/.jsx"),
    )
    for check_name, label, files, command_factory, timeout, extensions in checks:
        failures = 0
        timeouts = 0
        for path in files:
            code, output, timed_out = run_check(command_factory(path), timeout)
            if timed_out:
                timeouts += 1
            elif code != 0:
                failures += 1
            if output.strip():
                output_parts.append(f"=== Sintaxe {label}: {path.relative_to(ROOT)} ===\n{output}")
        if files:
            state = "timeout" if timeouts else ("failed" if failures else "passed")
            results.append({"name": check_name, "status": state,
                            "files_checked": len(files), "failures": failures})
            output_parts.append(
                f"Verificação {label}: {len(files)} arquivo(s), {failures} falha(s), {timeouts} timeout(s)."
            )
        else:
            results.append({"name": check_name, "status": "skipped", "files_checked": 0})
            output_parts.append(f"Nenhum arquivo compatível {extensions} encontrado.")

    if scan_incomplete:
        output_parts.append(
            "AVISO: a varredura de código atingiu limites de quantidade/tamanho; "
            "alguns arquivos podem não ter sido verificados."
        )

    failures = any(item["status"] in {"failed", "timeout"} for item in results)
    executed = any(item["status"] in {"passed", "failed", "timeout"} for item in results)
    status = "failed" if failures else ("inconclusive" if scan_incomplete else ("passed" if executed else "not_applicable"))
    output = "\n\n".join(output_parts)
    print(output[-MAX_CAPTURE_BYTES:])
    print("\nRESULTADO_JSON=" + json.dumps({
        "status": status, "checks": results, "javascript_scan_incomplete": scan_incomplete
    }, ensure_ascii=False))
    return 0 if status in {"passed", "not_applicable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
