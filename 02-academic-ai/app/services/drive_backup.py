from __future__ import annotations

import asyncio
import hashlib
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
APP_DOC_ID_KEY = "academic_ai_doc_id"
APP_SUBJECT_KEY = "academic_ai_subject"
APP_SHA256_KEY = "academic_ai_sha256"
DB_FOLDER_NAME = "_backup"
DB_DOC_ID = "academic-ai:database"
DB_FILE_NAME = "academic_ai.db"


class DriveBackupError(RuntimeError):
    """Base error for Google Drive backup failures."""


class DriveNotAuthorized(DriveBackupError):
    """Credentials/token file missing or no longer refreshable."""


class DriveBackupService:
    """Best-effort backup of ingested PDFs to Google Drive.

    Layout: ``<root>/<SUBJECT_CODE>/<original_name>``. Uploads carry
    appProperties (document id, subject, sha256) so re-uploads of identical
    content are skipped and deletions can find their remote copy. All blocking
    Google API calls run in worker threads. Callers must treat every failure
    as non-fatal: local files, SQLite, and RAG never depend on Drive.
    """

    def __init__(
        self,
        *,
        credentials_file: Path,
        token_file: Path,
        root_folder_name: str = "Academic_AI",
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.root_folder_name = root_folder_name.strip() or "Academic_AI"
        self._client_factory = client_factory
        self._folder_cache: dict[str, str] = {}

    async def backup_document(
        self,
        *,
        subject_code: str,
        original_name: str,
        local_path: Path,
        document_id: str,
        sha256: str,
    ) -> str | None:
        """Upload one PDF (or reuse the identical remote copy); return Drive file ID."""
        return await asyncio.to_thread(
            self._backup_sync,
            subject_code,
            original_name,
            Path(local_path),
            document_id,
            sha256,
        )

    async def delete_document_backup(
        self,
        document_id: str,
        drive_file_id: str | None = None,
    ) -> bool:
        """Delete remote copies of one document; True when anything was removed."""
        return await asyncio.to_thread(self._delete_sync, document_id, drive_file_id)

    async def backup_database(self, *, local_path: Path, sha256: str) -> str | None:
        """Upload a DB snapshot (or reuse the identical copy); return Drive file ID."""
        return await asyncio.to_thread(self._backup_database_sync, Path(local_path), sha256)

    def _service(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        if not self.credentials_file.is_file():
            raise DriveNotAuthorized(
                f"File kredensial Google tidak ditemukan: {self.credentials_file}. "
                "Lihat PANDUAN_GDRIVE_BACKUP.md, lalu jalankan: python run.py --drive-auth"
            )
        if not self.token_file.is_file():
            raise DriveNotAuthorized(
                f"Token Drive belum ada: {self.token_file}. Jalankan: python run.py --drive-auth"
            )
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise DriveBackupError(
                "Library Google Drive belum terinstal. Jalankan: pip install -r requirements.txt"
            ) from exc
        creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.token_file.write_text(creds.to_json(), encoding="utf-8")
            else:
                raise DriveNotAuthorized(
                    "Token Drive kedaluwarsa dan tidak bisa di-refresh. "
                    "Jalankan ulang: python run.py --drive-auth"
                )
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def _backup_sync(
        self,
        subject_code: str,
        original_name: str,
        local_path: Path,
        document_id: str,
        sha256: str,
    ) -> str | None:
        service = self._service()
        root_id = self._find_or_create_folder(service, self.root_folder_name, None)
        subject_id = self._find_or_create_folder(service, subject_code, root_id)
        existing = self._find_same_content(service, subject_id, original_name, sha256)
        if existing:
            logger.info(
                "[INFO] Backup Drive dilewati (konten identik sudah ada): %s", original_name
            )
            return existing
        return self._upload_new(
            service, subject_id, original_name, local_path, document_id, subject_code, sha256
        )

    def _backup_database_sync(self, local_path: Path, sha256: str) -> str | None:
        service = self._service()
        root_id = self._find_or_create_folder(service, self.root_folder_name, None)
        folder_id = self._find_or_create_folder(service, DB_FOLDER_NAME, root_id)
        existing = self._find_same_content(service, folder_id, DB_FILE_NAME, sha256)
        if existing:
            logger.info("[INFO] Backup database Drive dilewati (konten identik sudah ada)")
            return existing
        return self._upload_new(
            service,
            folder_id,
            DB_FILE_NAME,
            local_path,
            DB_DOC_ID,
            "database",
            sha256,
            mimetype="application/x-sqlite3",
            kind_label="Database",
        )

    def _delete_sync(self, document_id: str, drive_file_id: str | None) -> bool:
        service = self._service()
        if drive_file_id:
            try:
                service.files().delete(fileId=drive_file_id).execute()
                return True
            except Exception:
                logger.warning("[WARN] Hapus backup Drive by ID gagal; mencoba pencarian dokumen.")
        safe_doc = document_id.replace("'", "\\'")
        query = (
            f"appProperties has {{ key='{APP_DOC_ID_KEY}' and value='{safe_doc}' }} "
            "and trashed=false"
        )
        result = service.files().list(q=query, fields="files(id)").execute()
        deleted = False
        for item in result.get("files", []):
            service.files().delete(fileId=item["id"]).execute()
            deleted = True
        return deleted

    def _find_or_create_folder(self, service: Any, name: str, parent_id: str | None) -> str:
        cache_key = f"{parent_id or 'root'}//{name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]
        safe_name = name.replace("'", "\\'")
        query = (
            f"mimeType='application/vnd.google-apps.folder' and name='{safe_name}' "
            "and trashed=false"
        )
        if parent_id:
            query += f" and '{parent_id}' in parents"
        result = service.files().list(q=query, fields="files(id, name)", pageSize=10).execute()
        files = result.get("files", [])
        if files:
            folder_id = str(files[0]["id"])
        else:
            body: dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                body["parents"] = [parent_id]
            folder_id = str(service.files().create(body=body, fields="id").execute()["id"])
            logger.info("[INFO] Folder Drive dibuat: %s", name)
        self._folder_cache[cache_key] = folder_id
        return folder_id

    def _find_same_content(
        self, service: Any, folder_id: str, original_name: str, sha256: str
    ) -> str | None:
        safe_name = original_name.replace("'", "\\'")
        query = f"'{folder_id}' in parents and name='{safe_name}' and trashed=false"
        result = service.files().list(q=query, fields="files(id, appProperties)").execute()
        for item in result.get("files", []):
            props = item.get("appProperties") or {}
            if props.get(APP_SHA256_KEY) == sha256:
                return str(item["id"])
        return None

    def _upload_new(
        self,
        service: Any,
        folder_id: str,
        original_name: str,
        local_path: Path,
        document_id: str,
        subject_code: str,
        sha256: str,
        *,
        mimetype: str = "application/pdf",
        kind_label: str = "PDF",
    ) -> str:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(local_path), mimetype=mimetype, resumable=True)
        body = {
            "name": original_name,
            "parents": [folder_id],
            "appProperties": {
                APP_DOC_ID_KEY: document_id,
                APP_SUBJECT_KEY: subject_code,
                APP_SHA256_KEY: sha256,
            },
        }
        created = service.files().create(body=body, media_body=media, fields="id").execute()
        file_id = str(created["id"])
        logger.info("[INFO] %s dibackup ke Drive (%s): %s", kind_label, subject_code, original_name)
        return file_id


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def backup_database_snapshot(service: DriveBackupService, db_path: Path) -> str | None:
    """Snapshot a live SQLite file consistently, then back it up to Drive."""
    from app.database.database import Database

    with tempfile.TemporaryDirectory(prefix="academic_ai_db_") as tmp_dir:
        snapshot = await asyncio.to_thread(
            Database(db_path).snapshot_to, Path(tmp_dir) / DB_FILE_NAME
        )
        sha256 = await asyncio.to_thread(_sha256_of, snapshot)
        return await service.backup_database(local_path=snapshot, sha256=sha256)


def build_drive_backup(settings) -> DriveBackupService | None:
    """Return an enabled backup service, or None when GDRIVE_BACKUP_ENABLED is off."""
    if not getattr(settings, "gdrive_backup_enabled", False):
        return None
    logger.info("[INFO] Backup Google Drive aktif (root: %s)", settings.gdrive_root_folder)
    return DriveBackupService(
        credentials_file=settings.gdrive_credentials_file,
        token_file=settings.gdrive_token_file,
        root_folder_name=settings.gdrive_root_folder,
    )


def run_drive_auth(settings) -> None:
    """One-time OAuth authorization: opens a browser, then saves the token file."""
    credentials_file: Path = settings.gdrive_credentials_file
    token_file: Path = settings.gdrive_token_file
    if not credentials_file.is_file():
        raise DriveNotAuthorized(
            f"File kredensial Google tidak ditemukan: {credentials_file}. "
            "Unduh OAuth client (Desktop app) dari Google Cloud Console. "
            "Lihat PANDUAN_GDRIVE_BACKUP.md."
        )
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise DriveBackupError(
            "Library Google belum terinstal. Jalankan: pip install -r requirements.txt"
        ) from exc
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
    creds = flow.run_local_server(port=0)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Token Drive tersimpan: {token_file}")
