"""CLI Sinkronisasi & Impor Skill GitHub untuk MARU AI.

Contoh pemakaian (Windows CMD / PowerShell / Linux):
  python -m maru_github_sync status
  python -m maru_github_sync list-skills
  python -m maru_github_sync add-skill https://github.com/anthropics/skills/tree/main/skills/pdf --division academic
  python -m maru_github_sync push
  python -m maru_github_sync pull
  python -m maru_github_sync sync
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import GitHubSyncConfig
from .sync_service import MaruGitHubSyncService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="maru_github_sync",
        description="Sinkronisasi & manajemen Skill/Memori MARU AI dengan GitHub.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for simple_cmd in ("status", "export-local", "import-local", "push", "pull", "sync", "list-skills"):
        sub.add_parser(simple_cmd)

    add_p = sub.add_parser(
        "add-skill",
        help="Impor SKILL.md dari URL/repo GitHub mana pun ke MARU AI + auto-push.",
    )
    add_p.add_argument(
        "source",
        help="URL folder/file GitHub atau owner/repo/path (contoh: https://github.com/anthropics/skills/tree/main/skills/pdf)",
    )
    add_p.add_argument(
        "--division",
        "-d",
        choices=["academic", "social-media", "shared"],
        default="shared",
        help="Target divisi pengguna skill (default: shared = dipakai semua divisi).",
    )
    add_p.add_argument(
        "--name",
        "-n",
        default=None,
        help="Nama folder skill kustom (opsional; otomatis dideteksi dari frontmatter/URL).",
    )
    add_p.add_argument(
        "--no-push",
        action="store_true",
        help="Pasang secara lokal saja tanpa langsung push ke repo GitHub MARU.",
    )

    args = parser.parse_args(argv)
    cfg = GitHubSyncConfig.from_env()
    svc = MaruGitHubSyncService(cfg)

    try:
        if args.command == "status":
            local_files = [
                str(p.relative_to(cfg.repo_root)).replace("\\", "/")
                for p in svc.collect_syncable_files()
            ]
            info: dict = {
                "enabled": cfg.enabled,
                "repo": cfg.repo,
                "branch": cfg.branch,
                "token_configured": bool(cfg.token),
                "local_syncable_files": len(local_files),
            }
            if cfg.is_ready:
                info["remote"] = svc.client.check_repo()
            print(json.dumps(info, indent=2, ensure_ascii=False))
            return 0

        if args.command == "list-skills":
            svc._refresh_registry_and_index()
            reg_path = cfg.repo_root / "skills" / "REGISTRY.json"
            print(reg_path.read_text(encoding="utf-8"))
            return 0

        if args.command == "add-skill":
            res = svc.add_skill_from_github(
                args.source,
                division=args.division,
                custom_name=args.name,
                push_remote=not args.no_push,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0

        if args.command == "export-local":
            print(json.dumps(svc.export_local_to_central(), indent=2, ensure_ascii=False))
            return 0

        if args.command == "import-local":
            print(json.dumps(svc.import_central_to_local(), indent=2, ensure_ascii=False))
            return 0

        if args.command == "push":
            print(json.dumps(svc.push_skills_and_memory(), indent=2, ensure_ascii=False))
            return 0

        if args.command == "pull":
            print(json.dumps(svc.pull_skills_and_memory(), indent=2, ensure_ascii=False))
            return 0

        if args.command == "sync":
            pulled = svc.pull_skills_and_memory()
            pushed = svc.push_skills_and_memory()
            print(json.dumps({"pull": pulled, "push": pushed}, indent=2, ensure_ascii=False))
            return 0

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
