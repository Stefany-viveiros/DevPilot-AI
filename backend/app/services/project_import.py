from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile
from io import BytesIO
from uuid import uuid4

from app.core.config import (
    MAX_ARCHIVE_BYTES, MAX_ARCHIVE_FILES, MAX_EXTRACTED_BYTES,
    MAX_SINGLE_FILE_BYTES, WORKSPACE_DIR,
)

IGNORED_DIRECTORIES = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".next", "dist",
    "build", ".idea", ".vscode",
}
SENSITIVE_NAMES = {
    ".env", "id_rsa", "id_ed25519", "credentials", "credentials.json",
    "secrets.json",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
SENSITIVE_PARTS = ("secret", "credential", "token", "password", "api_key")

class ArchiveValidationError(ValueError):
    """Arquivo compactado inválido ou que viola os limites de importação."""

@dataclass(frozen=True)
class ImportResult:
    storage_path: str
    files_imported: int
    files_skipped: int
    bytes_imported: int

def _is_sensitive(relative_path: PurePosixPath) -> bool:
    for part in relative_path.parts:
        lower = part.lower()
        if lower in SENSITIVE_NAMES or lower.startswith(".env.") or lower.endswith(tuple(SENSITIVE_SUFFIXES)):
            return True
        if any(marker in lower for marker in SENSITIVE_PARTS):
            return True
    return False

def extract_project_archive(archive_bytes: bytes, workspace_dir: Path | None = None) -> ImportResult:
    if not archive_bytes:
        raise ArchiveValidationError("O arquivo enviado está vazio.")
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise ArchiveValidationError("O arquivo compactado excede o limite de 20 MB.")

    workspace = (workspace_dir or WORKSPACE_DIR).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    destination = (workspace / uuid4().hex).resolve()
    destination.mkdir(parents=False, exist_ok=False)
    imported = skipped = total_bytes = 0

    try:
        try:
            archive = zipfile.ZipFile(BytesIO(archive_bytes))
        except (zipfile.BadZipFile, OSError) as exc:
            raise ArchiveValidationError("O arquivo precisa ser um ZIP válido.") from exc

        with archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_FILES:
                raise ArchiveValidationError("O ZIP contém mais de 2.000 itens.")

            for info in entries:
                raw_name = info.filename.replace("\\", "/")
                relative = PurePosixPath(raw_name)
                if relative.is_absolute() or not relative.parts or any(
                    part in {"", ".", ".."} for part in relative.parts
                ) or (relative.parts and ":" in relative.parts[0]):
                    raise ArchiveValidationError("O ZIP contém um caminho de arquivo inválido.")

                unix_mode = info.external_attr >> 16
                file_type = stat.S_IFMT(unix_mode)
                if stat.S_ISLNK(unix_mode) or (file_type not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    skipped += 1
                    continue
                if info.is_dir():
                    continue
                if info.flag_bits & 0x1:
                    raise ArchiveValidationError("Não aceitamos ZIPs protegidos por senha.")
                if info.file_size > MAX_SINGLE_FILE_BYTES:
                    raise ArchiveValidationError("Um arquivo do ZIP excede o limite individual de 10 MB.")
                if info.file_size and info.compress_size == 0:
                    raise ArchiveValidationError("O ZIP contém uma entrada compactada inválida.")
                if info.compress_size and info.file_size / info.compress_size > 200:
                    raise ArchiveValidationError("O ZIP contém uma taxa de compressão excessiva.")

                if any(part.lower() in IGNORED_DIRECTORIES for part in relative.parts) or _is_sensitive(relative):
                    skipped += 1
                    continue

                total_bytes += info.file_size
                if total_bytes > MAX_EXTRACTED_BYTES:
                    raise ArchiveValidationError("O conteúdo descompactado excede o limite de 100 MB.")

                target = (destination / Path(*relative.parts)).resolve()
                if not target.is_relative_to(destination):
                    raise ArchiveValidationError("O ZIP tentou gravar fora da pasta do projeto.")
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info, "r") as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > MAX_SINGLE_FILE_BYTES or written > info.file_size:
                            raise ArchiveValidationError("O conteúdo real de um arquivo excedeu o limite declarado.")
                        output.write(chunk)
                if written != info.file_size:
                    raise ArchiveValidationError("Um arquivo do ZIP foi extraído de forma incompleta.")
                imported += 1

        if imported == 0:
            raise ArchiveValidationError("Nenhum arquivo permitido foi encontrado no ZIP.")
        return ImportResult(
            storage_path=str(destination.relative_to(workspace)),
            files_imported=imported,
            files_skipped=skipped,
            bytes_imported=total_bytes,
        )
    except zipfile.BadZipFile as exc:
        shutil.rmtree(destination, ignore_errors=True)
        raise ArchiveValidationError("O ZIP está danificado ou contém dados inconsistentes.") from exc
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
