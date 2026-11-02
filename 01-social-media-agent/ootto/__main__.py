"""CLI Ootto: python -m ootto <perintah>."""

from __future__ import annotations

import argparse
import json

from . import batalkan, jadwalkan, run_due, status


def main() -> None:
    ap = argparse.ArgumentParser(description="Ootto — penjadwal TikTok satu pemilik")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("schedule")
    p.add_argument("id")
    p.add_argument("waktu")
    p = sub.add_parser("status")
    p.add_argument("id")
    p = sub.add_parser("cancel")
    p.add_argument("id")
    sub.add_parser("run-due")
    args = ap.parse_args()
    if args.cmd == "schedule":
        out = jadwalkan(args.id, args.waktu)
    elif args.cmd == "status":
        out = status(args.id)
    elif args.cmd == "cancel":
        out = batalkan(args.id)
    else:
        out = run_due()
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
