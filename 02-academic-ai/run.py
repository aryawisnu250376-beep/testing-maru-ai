from __future__ import annotations

import argparse
import asyncio
import logging

from telegram import Update

from app.bot.telegram_bot import build_application
from app.config import Settings
from app.database.database import Database
from app.diagnostics import check_live_models, check_local_config
from app.knowledge.embeddings import EmbeddingService
from app.knowledge.vector_store import LocalVectorStore
from app.logging_setup import setup_logging
from app.manager.manager import AcademicManager
from app.providers.base import AIProvider
from app.providers.router import build_manager_provider, build_provider
from app.services.material_service import MaterialService


def _provider_for(settings: Settings) -> AIProvider:
    # Shared provider for specialists, embeddings, and STT (9Router by default).
    return build_provider(settings)


async def _close_providers(*providers: AIProvider | None) -> None:
    """Close each distinct provider once (the default Manager may share one)."""
    seen: set[int] = set()
    for provider in providers:
        if provider is None or id(provider) in seen:
            continue
        seen.add(id(provider))
        await provider.close()


async def _check_live(settings: Settings) -> int:
    provider = _provider_for(settings)
    manager_provider = build_manager_provider(settings, provider)
    try:
        return await check_live_models(settings, provider, manager_provider)
    finally:
        await _close_providers(provider, manager_provider)


def main() -> None:
    parser = argparse.ArgumentParser(description="Academic AI Telegram bot")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Periksa .env dan kelengkapan ID model tanpa menjalankan bot.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Dengan --check, cocokkan ID model ke katalog live.",
    )
    parser.add_argument(
        "--drive-auth",
        action="store_true",
        help="Login OAuth Google Drive sekali (buka browser), simpan token, lalu keluar.",
    )
    parser.add_argument(
        "--backup-db",
        action="store_true",
        help="Unggah snapshot database ke Google Drive sekali, lalu keluar.",
    )
    parser.add_argument(
        "--set-password",
        action="store_true",
        help="Ganti password login web di .env (interaktif), lalu keluar.",
    )
    args = parser.parse_args()

    logger = setup_logging("bot")

    tool_mode = args.drive_auth or args.backup_db or args.set_password
    try:
        settings = Settings.load(
            require_telegram=not tool_mode,
            require_router=not tool_mode,
        )
    except (ValueError, FileNotFoundError) as exc:
        logger.error("[ERROR] Konfigurasi belum siap: %s", exc)
        raise SystemExit(1) from exc

    configured_level = getattr(logging, settings.log_level, logging.INFO)
    logging.getLogger().setLevel(configured_level)

    if args.drive_auth:
        from app.services.drive_backup import run_drive_auth

        try:
            run_drive_auth(settings)
        except Exception as exc:
            logger.error("[ERROR] Otorisasi Google Drive gagal: %s", exc)
            raise SystemExit(1) from exc
        raise SystemExit(0)

    if args.backup_db:
        from app.services.drive_backup import backup_database_snapshot, build_drive_backup

        service = build_drive_backup(settings)
        if service is None:
            logger.error("[ERROR] Backup Drive mati. Set GDRIVE_BACKUP_ENABLED=true di .env.")
            raise SystemExit(1)
        if not settings.database_path.is_file():
            logger.error("[ERROR] Database belum ada; jalankan bot/web dulu.")
            raise SystemExit(1)
        try:
            file_id = asyncio.run(backup_database_snapshot(service, settings.database_path))
        except Exception as exc:
            logger.error("[ERROR] Backup database gagal: %s", exc)
            raise SystemExit(1) from exc
        if file_id:
            logger.info("[INFO] Database terbackup ke Drive (file ID: %s)", file_id)
        else:
            logger.info("[INFO] Database tidak berubah; backup dilewati.")
        raise SystemExit(0)

    if args.set_password:
        import getpass

        from app.settings_update import set_local_password

        try:
            first = getpass.getpass("Password web baru (min 8 karakter): ")
            second = getpass.getpass("Ulangi password: ")
        except (EOFError, KeyboardInterrupt):
            logger.error("[ERROR] Ganti password dibatalkan.")
            raise SystemExit(1) from None
        if first != second:
            logger.error("[ERROR] Password tidak sama; dibatalkan.")
            raise SystemExit(1)
        try:
            set_local_password(settings.env_file, first)
        except ValueError as exc:
            logger.error("[ERROR] %s", exc)
            raise SystemExit(1) from exc
        logger.info(
            "[INFO] Password tersimpan di %s. Restart web agar berlaku.",
            settings.env_file,
        )
        raise SystemExit(0)

    if args.live and not args.check:
        parser.error("Gunakan --live bersama --check, bukan sebagai argumen mandiri.")
    if args.check:
        local_status = check_local_config(settings)
        if args.live:
            try:
                live_status = asyncio.run(_check_live(settings))
            except Exception as exc:
                logger.error("[ERROR] Pemeriksaan live gagal (%s)", type(exc).__name__)
                live_status = 2
            if live_status == 2:
                raise SystemExit(2)
            raise SystemExit(1 if local_status or live_status else 0)
        raise SystemExit(local_status)

    if check_local_config(settings) != 0:
        raise SystemExit(1)
    logger.info("[INFO] Bot starting...")
    settings.prepare_local_directories()

    database = Database(settings.database_path)
    provider = _provider_for(settings)
    manager_provider = build_manager_provider(settings, provider)
    embedding_service = EmbeddingService(provider, settings.embedding_model)
    vector_store = LocalVectorStore(
        database,
        settings.vectorstore_dir / "vectors.sqlite",
    )
    academic_manager = AcademicManager(
        settings=settings,
        database=database,
        provider=provider,
        embedding_service=embedding_service,
        vector_store=vector_store,
        manager_provider=manager_provider,
    )
    material_service = MaterialService(
        settings,
        database,
        embedding_service,
        vector_store,
        drive_backup=build_drive_backup(settings),
    )

    application = build_application(
        settings=settings,
        database=database,
        provider=provider,
        academic_manager=academic_manager,
        material_service=material_service,
    )
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
