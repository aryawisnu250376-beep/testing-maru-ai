"""Patch kode berbasis AI: diagnosis error -> patch JSON -> backup -> uji -> simpan/rollback."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_TOP_FILES = {"web_run.py", "run.py"}
ALLOWED_DIRS = ("app", "tools")
MAX_PATCH_CHARS = 16000
MAX_FILE_CHARS = 24000

SYSTEM_PROMPT = (
    "Kamu adalah teknisi kode senior untuk aplikasi Python Academic AI. "
    "Tugasmu memperbaiki BUG pada kode sumber berdasarkan laporan error. "
    "Aturan keras: (1) patch kecil dan paling minimal; (2) hanya perbaiki bug yang "
    "dilaporkan, jangan menulis ulang fitur; (3) setiap patch berupa teks 'find' yang "
    "ADA PERSIS SATU KALI di file dan 'replace' sebagai penggantinya; (4) jangan ubah "
    "file .env, data, atau rahasia; (5) jika tidak yakin, kirim patches kosong. "
    "Balas SATU objek JSON valid saja: "
    '{"diagnosis":"...","patches":[{"file":"app/...","find_text":"...","replace_text":"..."}],'
    '"explanation":"...","needs_restart":false}'
)


@dataclass
class PatchResult:
    file: str
    applied: bool
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodeFixReport:
    diagnosis: str = ""
    explanation: str = ""
    patches: list[PatchResult] = field(default_factory=list)
    tests_passed: bool | None = None
    test_output_tail: str = ""
    kept: bool = False
    batch_id: str = ""
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["patches"] = [patch.as_dict() for patch in self.patches]
        return data


def _is_allowed_file(project_root: Path, rel: str) -> bool:
    candidate = (project_root / rel).resolve()
    try:
        candidate.relative_to(project_root.resolve())
    except ValueError:
        return False
    if candidate.suffix != ".py":
        return False
    parts = Path(rel).parts
    if not parts:
        return False
    if parts[0] in ALLOWED_DIRS:
        return True
    return len(parts) == 1 and parts[0] in ALLOWED_TOP_FILES


def apply_patch_file(
    project_root: Path,
    backup_root: Path,
    rel: str,
    find_text: str,
    replace_text: str,
) -> PatchResult:
    """Terapkan satu patch find/replace dengan backup. Find wajib muncul tepat sekali."""
    if not _is_allowed_file(project_root, rel):
        return PatchResult(rel, False, "file tidak diizinkan")
    if not find_text or find_text == replace_text:
        return PatchResult(rel, False, "find_text kosong/tidak berubah")
    if len(find_text) > MAX_PATCH_CHARS or len(replace_text) > MAX_PATCH_CHARS:
        return PatchResult(rel, False, "patch terlalu besar")
    target = project_root / rel
    if not target.is_file():
        return PatchResult(rel, False, "file tidak ditemukan")
    original = target.read_text(encoding="utf-8")
    if len(original) > MAX_FILE_CHARS:
        return PatchResult(rel, False, "file terlalu besar untuk dipatch otomatis")
    occurrences = original.count(find_text)
    if occurrences != 1:
        return PatchResult(rel, False, f"find_text ditemukan {occurrences}x (harus tepat 1)")
    backup_file = backup_root / rel
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_file)
    target.write_text(original.replace(find_text, replace_text, 1), encoding="utf-8")
    return PatchResult(rel, True, "diterapkan")


def rollback_batch(project_root: Path, backup_root: Path) -> list[str]:
    """Kembalikan semua file dari folder backup batch. Return daftar file yang dipulihkan."""
    restored: list[str] = []
    if not backup_root.is_dir():
        return restored
    for backup_file in backup_root.rglob("*"):
        if not backup_file.is_file():
            continue
        rel = backup_file.relative_to(backup_root)
        target = project_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, target)
        restored.append(rel.as_posix())
    return restored


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:] if lines and lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].strip() == "```" else lines
        cleaned = "\n".join(lines).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("JSON tidak ditemukan")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON root harus objek")
    return payload


def collect_error_context(errors: list[dict[str, Any]], project_root: Path, max_files: int = 3) -> str:
    """Susun konteks: daftar error + isi file yang disebut di traceback/pesan."""
    parts: list[str] = ["## Laporan error terkini"]
    for item in errors[:8]:
        parts.append(f"- [{item.get('ts', '?')}] {item.get('message', '')[:240]}")
    mentioned: list[str] = []
    blob = " ".join(str(item.get("message", "")) for item in errors)
    for match in re.finditer(r"([\w/\\]+\.py)", blob):
        rel = match.group(1).replace("\\", "/")
        rel = rel.split("app/", 1)[-1] if "app/" in rel and not rel.startswith("app/") else rel
        if rel not in mentioned and _is_allowed_file(project_root, rel):
            mentioned.append(rel)
    for rel in mentioned[:max_files]:
        target = project_root / rel
        try:
            text = target.read_text(encoding="utf-8")[:MAX_FILE_CHARS]
        except OSError:
            continue
        parts.append(f"\n## File {rel}\n```\n{text}\n```")
    return "\n".join(parts)


async def run_tests(project_root: Path, test_command: list[str] | None, timeout: float = 300.0) -> tuple[bool, str]:
    if test_command is None:
        return True, "(uji dilewati)"
    try:
        process = await asyncio.create_subprocess_exec(
            *test_command,
            cwd=str(project_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        output = (stdout or b"").decode("utf-8", errors="replace")
        return process.returncode == 0, output[-1500:]
    except asyncio.TimeoutError:
        return False, "uji melewati batas waktu"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


async def diagnose_and_fix(
    *,
    settings: Any,
    provider: Any,
    errors: list[dict[str, Any]],
    project_root: Path | None = None,
    test_command: list[str] | None = None,
    max_patches: int = 3,
) -> CodeFixReport:
    """Minta model mendiagnosis error, terapkan patch aman, uji, simpan atau rollback."""
    root = Path(project_root or getattr(settings, "project_root", ".")).resolve()
    report = CodeFixReport()
    if not errors:
        report.diagnosis = "Tidak ada error untuk dianalisis."
        return report

    context = collect_error_context(errors, root)
    model = getattr(settings, "manager_model", "")
    candidates = [model] if model else []
    try:
        candidates += [m for m in await provider.list_models() if m not in candidates][:2]
    except Exception:  # noqa: BLE001
        pass
    raw = ""
    last_exc: Exception | None = None
    for candidate in [c for c in candidates if c][:3]:
        try:
            raw, model = await provider.chat(
                candidate,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": context},
                ],
                temperature=0.0,
                max_tokens=2500,
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    if not raw:
        report.error = f"Model tidak dapat dihubungi ({type(last_exc).__name__ if last_exc else 'tidak ada model'})."
        return report

    try:
        payload = _extract_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        report.error = f"Model mengirim JSON tidak valid ({exc})."
        return report

    report.diagnosis = str(payload.get("diagnosis", ""))[:600]
    report.explanation = str(payload.get("explanation", ""))[:600]
    patches = payload.get("patches", [])
    if not isinstance(patches, list):
        report.error = "Format patches tidak valid."
        return report

    batch_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(getattr(settings, "data_dir", Path("data"))) / "patches" / batch_id / "originals"
    report.batch_id = batch_id
    applied_any = False
    for patch in patches[:max_patches]:
        if not isinstance(patch, dict):
            continue
        rel = str(patch.get("file", "")).strip().replace("\\", "/")
        find_text = str(patch.get("find_text", ""))
        replace_text = str(patch.get("replace_text", ""))
        result = apply_patch_file(root, backup_root, rel, find_text, replace_text)
        report.patches.append(result)
        applied_any = applied_any or result.applied

    if not applied_any:
        report.kept = False
        return report

    passed, tail = await run_tests(root, test_command)
    report.tests_passed = passed
    report.test_output_tail = tail
    if passed:
        report.kept = True
        manifest = {
            "batch_id": batch_id,
            "diagnosis": report.diagnosis,
            "files": [patch.file for patch in report.patches if patch.applied],
        }
        backup_root.parent.mkdir(parents=True, exist_ok=True)
        (backup_root.parent / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
    else:
        restored = rollback_batch(root, backup_root)
        report.kept = False
        report.explanation = (report.explanation + f" | Uji gagal, {len(restored)} file di-rollback.").strip()
        logger.warning("[TECH] Patch AI gagal uji, batch %s di-rollback", batch_id)
    return report


def rollback_last(settings: Any, project_root: Path | None = None) -> dict[str, Any]:
    """Rollback batch patch AI terakhir yang tersimpan."""
    root = Path(project_root or getattr(settings, "project_root", ".")).resolve()
    patches_dir = Path(getattr(settings, "data_dir", Path("data"))) / "patches"
    if not patches_dir.is_dir():
        return {"ok": False, "detail": "Belum ada patch AI yang tersimpan."}
    batches = sorted((path for path in patches_dir.iterdir() if path.is_dir()), reverse=True)
    for batch in batches:
        manifest_file = batch / "manifest.json"
        if not manifest_file.is_file():
            continue
        restored = rollback_batch(root, batch / "originals")
        manifest_file.unlink(missing_ok=True)
        return {"ok": True, "batch_id": batch.name, "restored": restored}
    return {"ok": False, "detail": "Tidak ada batch dengan manifest yang bisa di-rollback."}
