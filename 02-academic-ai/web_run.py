from __future__ import annotations

import asyncio

import uvicorn

from app.config import Settings
from app.database.database import Database
from app.knowledge.embeddings import EmbeddingService
from app.knowledge.vector_store import LocalVectorStore
from app.logging_setup import setup_logging
from app.manager.manager import AcademicManager
from app.providers.router import build_manager_provider, build_provider
from app.services.drive_backup import build_drive_backup
from app.services.material_service import MaterialService
from app.web.api import create_app


def main() -> None:
    logger = setup_logging("web")
    try:
        settings = Settings.load(require_telegram=False)
    except (ValueError, FileNotFoundError) as exc:
        logger.error("[ERROR] Konfigurasi belum siap: %s", exc)
        raise SystemExit(1) from exc
    if not settings.local_api_token:
        logger.error("[ERROR] Isi LOCAL_API_TOKEN di .env sebelum menjalankan website.")
        raise SystemExit(1)

    settings.prepare_local_directories()
    database = Database(settings.database_path)
    provider = build_provider(settings)
    manager_provider = build_manager_provider(settings, provider)
    embedding_service = EmbeddingService(provider, settings.embedding_model)
    vector_store = LocalVectorStore(database, settings.vectorstore_dir / "vectors.sqlite")
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

    async def serve() -> None:
        try:
            await database.initialize(settings.subjects)
            await database.upsert_user(0, "local-web", "Local Web")
            count = await vector_store.sync_from_database(set(settings.subjects))
            logger.info("[INFO] Local database ready (%s vector chunks synced)", count)
            app = create_app(
                settings=settings,
                database=database,
                academic_manager=academic_manager,
                material_service=material_service,
            )
            if settings.web_access_mode == "lan":
                logger.warning(
                    "[WARN] LAN mode aktif: dari HP buka http://<IP-LAPTOP>:%s pada jaringan Wi-Fi/private yang sama. "
                    "Jangan gunakan IP publik atau port forwarding.",
                    settings.web_port,
                )
            else:
                logger.info(
                    "[INFO] Website/API localhost-only: http://127.0.0.1:%s",
                    settings.web_port,
                )
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    host=settings.web_host,
                    port=settings.web_port,
                    access_log=False,
                    log_level=settings.log_level.lower(),
                )
            )
            await server.serve()
        finally:
            providers = (provider, manager_provider)
            seen: set[int] = set()
            for configured_provider in providers:
                if id(configured_provider) in seen:
                    continue
                seen.add(id(configured_provider))
                await configured_provider.close()
            logger.info("[INFO] AI providers closed")

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("[INFO] Website stopped by user.")


if __name__ == "__main__":
    main()
