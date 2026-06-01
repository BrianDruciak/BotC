"""
Command-line interface for the BOTC win-rate agent.

  python -m app.cli init-db
  python -m app.cli inspect data/games.xlsx
  python -m app.cli import  data/games.xlsx [--commit-clean-only] [--limit N] [--extractor gemini|stub]
  python -m app.cli demo    [--games 25]          # populate with stub data to test the pipeline
  python -m app.cli stats   [--min-games 1]
  python -m app.cli reset                          # delete the games DB
"""

from __future__ import annotations

import argparse
import json
import os

from . import db, ingest, stats
from .extract.base import get_extractor


def cmd_init_db(args):
    db.init_db(args.db)
    print(f"Initialized DB at {args.db}")


def cmd_inspect(args):
    from .importer import inspect
    print(json.dumps(inspect(args.path), indent=2, default=str))


def cmd_import(args):
    from .importer import import_sheet
    extractor = get_extractor(args.extractor) if args.extractor else None
    summary = import_sheet(
        args.path,
        db_path=args.db,
        extractor=extractor,
        commit_clean_only=args.commit_clean_only,
        limit=args.limit,
    )
    print("\nImport summary:", json.dumps(summary, indent=2))


def cmd_demo(args):
    db.init_db(args.db)
    extractor = get_extractor("stub")
    committed = 0
    for i in range(args.games):
        extraction = extractor.extract([f"demo-game-{i}".encode()])
        resolved = ingest.resolve(extraction)
        resolved.external_id = f"demo-{i+1}"
        ingest.commit(resolved, args.db)
        committed += 1
    print(f"Committed {committed} demo games to {args.db}")
    _print_stats(args.db, min_games=1)


def cmd_stats(args):
    _print_stats(args.db, min_games=args.min_games)


def cmd_reset(args):
    if os.path.exists(args.db):
        os.remove(args.db)
        print(f"Deleted {args.db}")
    else:
        print("No DB to delete.")


def _print_stats(db_path, min_games=0):
    ov = stats.overview(db_path)
    print("\n=== Overview ===")
    print(f"  games={ov['games']}  seats={ov['seats']}  players={ov['players']}")
    print(f"  good wins={ov['good_wins']} ({ov['good_win_pct']}%)  evil wins={ov['evil_wins']}")
    print(f"  games needing review: {ov['games_need_review']}")

    chars = stats.character_stats(db_path, min_games=min_games)
    print(f"\n=== Top characters by win% (min {min_games} games) ===")
    print(f"  {'character':22} {'type':10} {'G':>3} {'W':>3} {'win%':>6}")
    for c in chars[:15]:
        print(f"  {c['name']:22} {c['type']:10} {c['games']:>3} {c['wins']:>3} {c['win_pct']:>6}")

    players = stats.player_stats(db_path, min_games=min_games)
    print(f"\n=== Players by win% (min {min_games} games) ===")
    print(f"  {'player':16} {'G':>3} {'W':>3} {'win%':>6}  good%  evil%")
    for p in players[:15]:
        gp = "-" if p["good_win_pct"] is None else p["good_win_pct"]
        ep = "-" if p["evil_win_pct"] is None else p["evil_win_pct"]
        print(f"  {p['name']:16} {p['games']:>3} {p['wins']:>3} {p['win_pct']:>6}  {gp:>5}  {ep:>5}")


def build_parser():
    p = argparse.ArgumentParser(prog="botc", description="BOTC win-rate agent")
    p.add_argument("--db", default=db.DEFAULT_DB, help="SQLite DB path")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)

    sp = sub.add_parser("inspect")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("import")
    sp.add_argument("path")
    sp.add_argument("--extractor", choices=["gemini", "stub"], default=None)
    sp.add_argument("--commit-clean-only", action="store_true")
    sp.add_argument("--limit", type=int, default=None)
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("demo")
    sp.add_argument("--games", type=int, default=25)
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("stats")
    sp.add_argument("--min-games", type=int, default=0)
    sp.set_defaults(func=cmd_stats)

    sub.add_parser("reset").set_defaults(func=cmd_reset)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
