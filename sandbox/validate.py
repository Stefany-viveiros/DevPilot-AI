import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path("/workspace")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "coverage"}
MAX_JS_FILES = 100
MAX_JS_FILE_BYTES = 1_000_000
MAX_JS_TOTAL_BYTES = 20_000_000
MAX_CAPTURE_BYTES = 12_000
JS_SUFFIXES = {".js", ".mjs", ".cjs"}


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


def discover_javascript():
    found = []
    total_bytes = 0
    incomplete = False
    for current, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS
                   and not (Path(current) / name).is_symlink()]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() not in JS_SUFFIXES or path.is_symlink():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                incomplete = True
                continue
            if size > MAX_JS_FILE_BYTES or total_bytes + size > MAX_JS_TOTAL_BYTES:
                incomplete = True
                continue
            found.append(path)
            total_bytes += size
            if len(found) > MAX_JS_FILES:
                incomplete = True
                return found[:MAX_JS_FILES], incomplete
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

    js_files, js_incomplete = discover_javascript()
    js_failures = 0
    js_timeouts = 0
    for path in js_files:
        code, output, timed_out = run_check(["node", "--check", str(path)], 5)
        if timed_out:
            js_timeouts += 1
        elif code != 0:
            js_failures += 1
        if output.strip():
            output_parts.append(f"=== Sintaxe JavaScript: {path.relative_to(ROOT)} ===\n{output}")
    if js_files:
        js_status = "timeout" if js_timeouts else ("failed" if js_failures else "passed")
        results.append({"name": "javascript_syntax", "status": js_status,
                        "files_checked": len(js_files), "failures": js_failures})
        output_parts.append(
            f"Verificação de sintaxe JavaScript: {len(js_files)} arquivo(s), "
            f"{js_failures} falha(s), {js_timeouts} timeout(s)."
        )
    else:
        results.append({"name": "javascript_syntax", "status": "skipped", "files_checked": 0})
        output_parts.append("Nenhum arquivo JavaScript compatível (.js, .mjs, .cjs) encontrado.")
    if js_incomplete:
        output_parts.append(
            "AVISO: a varredura JavaScript atingiu limites de quantidade/tamanho; "
            "alguns arquivos podem não ter sido verificados."
        )

    failures = any(item["status"] in {"failed", "timeout"} for item in results)
    executed = any(item["status"] in {"passed", "failed", "timeout"} for item in results)
    status = "failed" if failures else ("inconclusive" if js_incomplete else ("passed" if executed else "not_applicable"))
    exit_code = 1 if failures else (0 if executed and not js_incomplete else None)
    output = "\n\n".join(output_parts)
    print(output[-MAX_CAPTURE_BYTES:])
    print("\\nRESULTADO_JSON=" + __import__("json").dumps({
        "status": status, "checks": results, "javascript_scan_incomplete": js_incomplete
    }, ensure_ascii=False))
    return 0 if status in {"passed", "not_applicable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
