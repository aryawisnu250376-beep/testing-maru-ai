from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers.admin import reset_command, status_command
from app.bot.handlers.chat import chat_message
from app.bot.handlers.delete_material import (
    delete_cancel_callback,
    delete_confirm_callback,
    delete_material_command,
    delete_select_callback,
)
from app.bot.handlers.discover import jelaskan_command, web_command
from app.bot.handlers.material import (
    add_material_command,
    materials_command,
    receive_document,
    upload_subject_callback,
)
from app.bot.handlers.mode import mode_callback, mode_command
from app.bot.handlers.start import help_command, start_command
from app.bot.handlers.study import quiz_command, summary_command
from app.bot.handlers.subject import matkul_command, subject_selection_callback
from app.bot.handlers.video import video_command
from app.config import Settings
from app.database.database import Database
from app.knowledge.vector_store import LocalVectorStore
from app.manager.manager import AcademicManager
from app.providers.base import AIProvider
from app.services.material_service import MaterialService

logger = logging.getLogger(__name__)


async def _post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    database: Database = application.bot_data["database"]
    provider: AIProvider = application.bot_data["provider"]
    vector_store: LocalVectorStore = application.bot_data["vector_store"]

    settings.prepare_local_directories()
    await database.initialize(settings.subjects)
    indexed_chunks = await vector_store.sync_from_database(set(settings.subjects))
    logger.info("[INFO] Database loaded (%s vector chunks synced)", indexed_chunks)

    chat_url = getattr(provider, "base_url", settings.chat_base_url)
    try:
        model_ids = await provider.list_models()
        logger.info(
            "[INFO] Specialist chat endpoint connected at %s (%s model IDs listed)",
            chat_url,
            len(model_ids),
        )
    except Exception as exc:
        # The process may start before the local 9Router/Ollama process. Keep Telegram alive;
        # a later AI request will show a helpful message if the gateway is still down.
        logger.warning(
            "[WARN] Specialist chat endpoint not reachable at %s (%s). Startup continues.",
            chat_url,
            type(exc).__name__,
        )

    manager_provider: AIProvider = application.bot_data.get("manager_provider", provider)
    if manager_provider is not provider:
        manager_url = getattr(manager_provider, "base_url", "?")
        try:
            model_ids = await manager_provider.list_models()
            logger.info(
                "[INFO] Manager chat endpoint connected at %s (%s model IDs listed)",
                manager_url,
                len(model_ids),
            )
        except Exception as exc:
            logger.warning(
                "[WARN] Manager chat endpoint not reachable at %s (%s). Startup continues.",
                manager_url,
                type(exc).__name__,
            )

    bot_identity = await application.bot.get_me()
    logger.info("[INFO] Telegram bot connected (@%s)", bot_identity.username or "bot")
    logger.info("[INFO] Research & Librarian team, subject specialists, and AI Manager ready")


async def _post_shutdown(application: Application) -> None:
    providers = (
        application.bot_data.get("provider"),
        application.bot_data.get("manager_provider"),
    )
    seen: set[int] = set()
    for provider in providers:
        if provider is None or id(provider) in seen:
            continue
        seen.add(id(provider))
        await provider.close()
    logger.info("[INFO] AI providers closed")


def build_application(
    *,
    settings: Settings,
    database: Database,
    provider: AIProvider,
    academic_manager: AcademicManager,
    material_service: MaterialService,
) -> Application:
    application = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data.update(
        {
            "settings": settings,
            "database": database,
            "provider": provider,
            "manager_provider": getattr(academic_manager, "manager_provider", provider),
            "academic_manager": academic_manager,
            "material_service": material_service,
            "vector_store": academic_manager.vector_store,
        }
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("matkul", matkul_command))
    application.add_handler(CommandHandler("tambahmateri", add_material_command))
    application.add_handler(CommandHandler("materi", materials_command))
    application.add_handler(CommandHandler("ringkas", summary_command))
    application.add_handler(CommandHandler("kuis", quiz_command))
    application.add_handler(CommandHandler("hapusmateri", delete_material_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("mode", mode_command))
    application.add_handler(CommandHandler("video", video_command))
    application.add_handler(CommandHandler("jelaskan", jelaskan_command))
    application.add_handler(CommandHandler("web", web_command))

    application.add_handler(CallbackQueryHandler(subject_selection_callback, pattern=r"^subject:"))
    application.add_handler(CallbackQueryHandler(mode_callback, pattern=r"^mode:"))
    application.add_handler(CallbackQueryHandler(upload_subject_callback, pattern=r"^upload:"))
    application.add_handler(
        CallbackQueryHandler(delete_select_callback, pattern=r"^delete-select:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_confirm_callback, pattern=r"^delete-confirm:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_cancel_callback, pattern=r"^delete-cancel$")
    )
    application.add_handler(MessageHandler(filters.Document.ALL, receive_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
    return application
