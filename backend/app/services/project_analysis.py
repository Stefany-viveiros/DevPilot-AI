from __future__ import annotations
from pathlib import Path
from collections import Counter

SKIP_DIRECTORIES = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".next", "dist", "build",
}
MANIFESTS = {
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "Pipfile": "Python",
    "package.json": "Node.js / JavaScript",
    "tsconfig.json": "TypeScript",
    "composer.json": "PHP",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "Gemfile": "Ruby",
    "pom.xml": "Java",
    "build.gradle": "Java / Kotlin",
    "pubspec.yaml": "Dart / Flutter",
    "Dockerfile": "Docker",
    "index.html": "HTML",
}
EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "React (JSX)",
    ".ts": "TypeScript", ".tsx": "React (TSX)", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".java": "Java", ".kt": "Kotlin",
    ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby",
    ".sql": "SQL", ".sh": "Shell", ".yaml": "YAML", ".yml": "YAML",
}
ENTRYPOINT_NAMES = {
    "main.py", "app.py", "manage.py", "main.js", "index.js",
    "server.js", "index.ts", "main.ts", "index.html", "docker-compose.yml",
}

def analyze_project(root: Path, max_listed_files: int = 150) -> dict:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError("A pasta do projeto não foi encontrada.")
    languages: Counter[str] = Counter()
    manifests: set[str] = set()
    entrypoints: list[str] = []
    listed_files: list[str] = []
    total_files = 0

    for current, directories, filenames in __import__("os").walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name for name in directories
            if name.lower() not in SKIP_DIRECTORIES
            and not (current_path / name).is_symlink()
        ]
        for filename in filenames:
            file_path = current_path / filename
            if file_path.is_symlink() or not file_path.is_file():
                continue
            relative = file_path.relative_to(root).as_posix()
            if filename.lower() in {".env", ".env.local", "id_rsa", "id_ed25519"}:
                continue
            total_files += 1
            if filename in MANIFESTS:
                manifests.add(MANIFESTS[filename])
            if file_path.suffix.lower() in EXTENSIONS:
                languages[EXTENSIONS[file_path.suffix.lower()]] += 1
            if filename in ENTRYPOINT_NAMES:
                entrypoints.append(relative)
            if len(listed_files) < max_listed_files:
                listed_files.append(relative)

    detected = sorted(set(languages) | manifests)
    return {
        "detected_technologies": detected,
        "language_file_counts": dict(sorted(languages.items())),
        "manifest_hints": sorted(manifests),
        "entrypoints": sorted(entrypoints)[:50],
        "files": sorted(listed_files),
        "total_files": total_files,
        "files_listed": len(listed_files),
        "files_omitted_from_list": max(0, total_files - len(listed_files)),
    }
