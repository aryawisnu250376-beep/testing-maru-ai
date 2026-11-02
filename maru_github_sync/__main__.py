"""CLI Sinkronisasi GitHub untuk Skill & Memori MARU AI.

Contoh pemakaian (Windows CMD / PowerShell / Linux):
  python -m maru_github_sync status
  python -m maru_github_sync export-local
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
        description="Sinkronisasi penyimpanan Skill & Memori MARU AI ke GitHub.",
    )
    parser.add_argument(
        "command",
        choices=["status", "export-local", "import-local", "push", "pull", "sync"],
        help="Aksi sinkronisasi yang dijalankan.",
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

        if args.command == "export-local":
            res = svc.export_local_to_central()
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0

        if args.command == "import-local":
            res = svc.import_central_to_local()
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0

        if args.command == "push":
            res = svc.push_skills_and_memory()
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0

        if args.command == "pull":
            res = svc.pull_skills_and_memory()
            print(json.dumps(res, indent=2, ensure_ascii=False))
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
