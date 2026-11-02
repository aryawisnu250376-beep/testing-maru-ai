from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

from app.config import Subject
from app.database.database import Database
from app.services.drive_backup import (
    APP_DOC_ID_KEY,
    APP_SHA256_KEY,
    DriveBackupService,
    DriveNotAuthorized,
    build_drive_backup,
)

SUBJECTS = {"PP": Subject("PP", "Pendidikan Pancasila", "pp", "")}


class FakeFilesResource:
    """In-memory stand-in for the Drive v3 files() resource."""

    def __init__(self) -> None:
        self.folders: dict[tuple[str | None, str], str] = {}
        self.files: dict[str, dict] = {}
        self.created_bodies: list[dict] = []
        self.deleted: list[str] = []
        self._counter = 0

    @staticmethod
    def _op(payload):
        return SimpleNamespace(execute=lambda: payload)

    def list(self, q=None, fields=None, pageSize=None):
        query = q or ""
        if "mimeType='application/vnd.google-apps.folder'" in query:
            name = re.search(r"name='((?:\\'|[^'])*)'", query).group(1)
            parent = re.search(r"'([^']+)' in parents", query)
            parent_id = parent.group(1) if parent else None
            folder_id = self.folders.get((parent_id, name))
            found = [{"id": folder_id, "name": name}] if folder_id else []
            return self._op({"files": found})
        if "appProperties has" in query:
            value = re.search(r"value='((?:\\'|[^'])*)'", query).group(1)
            found = [
                {"id": file_id}
                for file_id, body in self.files.items()
                if (body.get("appProperties") or {}).get(APP_DOC_ID_KEY) == value
            ]
            return self._op({"files": found})
        name = re.search(r"name='((?:\\'|[^'])*)'", query).group(1)
        parent = re.search(r"'([^']+)' in parents", query).group(1)
        found = [
            {"id": file_id, "appProperties": body.get("appProperties") or {}}
            for file_id, body in self.files.items()
            if body.get("name") == name and parent in (body.get("parents") or [])
        ]
        return self._op({"files": found})

    def create(self, body=None, media_body=None, fields=None):
        self._counter += 1
        new_id = f"drive-{self._counter}"
        body = dict(body or {})
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            parents = body.get("parents") or [None]
            self.folders[(parents[0], body["name"])] = new_id
        else:
            self.files[new_id] = body
        self.created_bodies.append(body)
        return self._op({"id": new_id})

    def delete(self, fileId=None):
        self.deleted.append(fileId)
        self.files.pop(fileId, None)
        return self._op({})


class FakeDriveClient:
    def __init__(self, files: FakeFilesResource) -> None:
        self._files = files

    def files(self):
        return self._files


def _service(files: FakeFilesResource, **kwargs) -> DriveBackupService:
    return DriveBackupService(
        credentials_file=Path("creds.json"),
        token_file=Path("token.json"),
        root_folder_name=kwargs.get("root_folder_name", "Academic_AI"),
        client_factory=lambda: FakeDriveClient(files),
    )


def test_backup_creates_folders_and_uploads_with_metadata(tmp_path: Path) -> None:
    files = FakeFilesResource()
    service = _service(files)
    pdf = tmp_path / "materi.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    file_id = asyncio.run(
        service.backup_document(
            subject_code="PP",
            original_name="materi.pdf",
            local_path=pdf,
            document_id="doc-1",
            sha256="abc123",
        )
    )
    assert file_id == "drive-3"  # root folder + subject folder + file
    upload = files.created_bodies[-1]
    assert upload["name"] == "materi.pdf"
    assert upload["parents"] == [files.folders[("drive-1", "PP")]]
    assert upload["appProperties"][APP_DOC_ID_KEY] == "doc-1"
    assert upload["appProperties"][APP_SHA256_KEY] == "abc123"


def test_backup_skips_identical_content(tmp_path: Path) -> None:
    files = FakeFilesResource()
    service = _service(files)
    pdf = tmp_path / "materi.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    kwargs = {
        "subject_code": "PP",
        "original_name": "materi.pdf",
        "local_path": pdf,
        "document_id": "doc-1",
        "sha256": "abc123",
    }
    first = asyncio.run(service.backup_document(**kwargs))
    creates_before = len(files.created_bodies)
    second = asyncio.run(service.backup_document(**kwargs))
    assert second == first
    assert len(files.created_bodies) == creates_before


def test_delete_prefers_drive_file_id() -> None:
    files = FakeFilesResource()
    files.files["drive-9"] = {"name": "old.pdf"}
    service = _service(files)
    assert asyncio.run(service.delete_document_backup("doc-x", "drive-9")) is True
    assert files.deleted == ["drive-9"]


def test_delete_falls_back_to_document_query() -> None:
    files = FakeFilesResource()
    files.files["drive-7"] = {"name": "a.pdf", "appProperties": {APP_DOC_ID_KEY: "doc-y"}}
    service = _service(files)
    assert asyncio.run(service.delete_document_backup("doc-y")) is True
    assert files.deleted == ["drive-7"]
    assert asyncio.run(service.delete_document_backup("missing")) is False


def test_service_without_token_raises_before_touching_google(tmp_path: Path) -> None:
    service = DriveBackupService(
        credentials_file=tmp_path / "no-creds.json",
        token_file=tmp_path / "no-token.json",
    )
    try:
        service._service()
    except DriveNotAuthorized:
        return
    raise AssertionError("expected DriveNotAuthorized for missing credentials")


def test_build_drive_backup_respects_flag() -> None:
    assert build_drive_backup(SimpleNamespace(gdrive_backup_enabled=False)) is None
    settings = SimpleNamespace(
        gdrive_backup_enabled=True,
        gdrive_credentials_file=Path("c.json"),
        gdrive_token_file=Path("t.json"),
        gdrive_root_folder="Root",
    )
    service = build_drive_backup(settings)
    assert isinstance(service, DriveBackupService)
    assert service.root_folder_name == "Root"


def test_material_hooks_are_best_effort_and_persist_drive_id(tmp_path: Path) -> None:
    from app.services.material_service import MaterialService

    async def scenario():
        database = Database(tmp_path / "test.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(1, "u", "U")
        await database.add_document_and_chunks(
            {
                "id": "doc-1",
                "subject_code": "PP",
                "original_name": "m.pdf",
                "stored_path": "data/knowledge/pp/m.pdf",
                "sha256": "s",
                "embedding_model": "e",
                "file_size_bytes": 10,
                "page_count": 1,
                "uploaded_by": 1,
            },
            [],
        )

        class RecordingBackup:
            def __init__(self):
                self.backups = []
                self.deletes = []

            async def backup_document(self, **kwargs):
                self.backups.append(kwargs)
                return "drive-42"

            async def delete_document_backup(self, document_id, drive_file_id=None):
                self.deletes.append((document_id, drive_file_id))
                return True

        settings = SimpleNamespace(project_root=tmp_path, knowledge_dir=tmp_path)
        dummy_store = SimpleNamespace()
        service = MaterialService(
            settings, database, None, dummy_store, drive_backup=RecordingBackup()
        )
        drive_id = await service._backup_to_drive_best_effort(
            subject_code="PP",
            original_name="m.pdf",
            stored_file=tmp_path / "m.pdf",
            document_id="doc-1",
            sha256="s",
        )
        assert drive_id == "drive-42"
        stored = await database.get_document("PP", "doc-1")
        assert stored["drive_file_id"] == "drive-42"
        await service._delete_drive_backup_best_effort("doc-1", stored)
        assert service.drive_backup.deletes == [("doc-1", "drive-42")]

        class FailingBackup(RecordingBackup):
            async def backup_document(self, **kwargs):
                raise RuntimeError("drive down")

        failing = MaterialService(
            settings, database, None, dummy_store, drive_backup=FailingBackup()
        )
        assert (
            await failing._backup_to_drive_best_effort(
                subject_code="PP",
                original_name="m.pdf",
                stored_file=tmp_path / "m.pdf",
                document_id="doc-1",
                sha256="s",
            )
            is None
        )

    asyncio.run(scenario())


def test_backup_database_uploads_to_backup_folder_and_dedups(tmp_path: Path) -> None:
    from app.services.drive_backup import DB_DOC_ID, DB_FILE_NAME, DB_FOLDER_NAME

    files = FakeFilesResource()
    service = _service(files)
    db_file = tmp_path / "academic_ai.db"
    db_file.write_bytes(b"sqlite-fake-bytes")

    async def run_uploads():
        first = await service.backup_database(local_path=db_file, sha256="dbsha1")
        creates_after_first = len(files.created_bodies)
        second = await service.backup_database(local_path=db_file, sha256="dbsha1")
        changed = await service.backup_database(local_path=db_file, sha256="dbsha2")
        return first, creates_after_first, second, changed

    first, creates_after_first, second, changed = asyncio.run(run_uploads())
    assert first is not None and second == first
    assert changed is not None and changed != first
    assert len(files.created_bodies) == creates_after_first + 1
    bodies = [body for body in files.created_bodies if body.get("name") == DB_FILE_NAME]
    assert len(bodies) == 2
    assert bodies[0]["parents"] == [files.folders[("drive-1", DB_FOLDER_NAME)]]
    assert bodies[0]["appProperties"][APP_DOC_ID_KEY] == DB_DOC_ID


def test_snapshot_to_produces_valid_copy(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "src.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(7, "snap", "Snap")
        copy = tmp_path / "copy.db"
        await asyncio.to_thread(database.snapshot_to, copy)
        probe = Database(copy)
        await probe.upsert_user(8, "probe-write", "P")
        assert await probe.get_subject_counts("PP") == (0, 0)
        assert await probe.get_web_session("nope") is None

    asyncio.run(scenario())


def test_database_backup_snapshot_and_hook_are_best_effort(tmp_path: Path) -> None:
    from app.services.drive_backup import backup_database_snapshot
    from app.services.material_service import MaterialService

    async def scenario() -> None:
        database = Database(tmp_path / "hook.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(1, "u", "U")
        calls: list[tuple[str, str]] = []

        class RecordingDBBackup:
            async def backup_database(self, *, local_path, sha256):
                calls.append((Path(local_path).name, sha256))
                assert Path(local_path).is_file()
                return "drive-db-1"

        file_id = await backup_database_snapshot(RecordingDBBackup(), database.path)
        assert file_id == "drive-db-1"
        assert calls and calls[0][0] == "academic_ai.db"

        settings = SimpleNamespace(project_root=tmp_path, knowledge_dir=tmp_path)
        service = MaterialService(
            settings, database, None, SimpleNamespace(), drive_backup=RecordingDBBackup()
        )
        assert await service._backup_database_best_effort() == "drive-db-1"

        class FailingDBBackup:
            async def backup_database(self, **kwargs):
                raise RuntimeError("drive down")

        failing = MaterialService(
            settings, database, None, SimpleNamespace(), drive_backup=FailingDBBackup()
        )
        assert await failing._backup_database_best_effort() is None
        disabled = MaterialService(settings, database, None, SimpleNamespace())
        assert await disabled._backup_database_best_effort() is None

    asyncio.run(scenario())
