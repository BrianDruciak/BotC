"""Apply the three manual games to manual_player_stats.json (delta on original sheet)."""

from __future__ import annotations

import json

from app.manual_stats import DEFAULT_JSON

# (player_name, alignment, won)
THREE_GAMES: list[list[tuple[str, str, bool]]] = [
    [
        ("PMA", "evil", True),
        ("Solomon", "evil", True),
        ("meiji", "good", False),
        ("4b", "good", False),
        ("Snail", "good", False),
        ("Paul", "good", False),
    ],
    [
        ("Seika", "good", True),
        ("Solomon", "good", True),
        ("Hautp", "good", True),
        ("Erika", "good", True),
        ("Tomato", "evil", False),
        ("Rice", "evil", False),
    ],
    [
        ("Solomon", "good", False),
        ("Kaptcha", "good", False),
        ("Paul", "good", False),
        ("Cube", "good", False),
        ("Rice", "good", False),
        ("Rendroken", "good", False),
        ("Marishi", "good", False),
        ("Evoker", "evil", True),
        ("Cercheo", "evil", True),
    ],
]


def _good_wins(p: dict) -> int:
    gg = p.get("good_games") or 0
    if not gg or p.get("good_win_pct") is None:
        return 0
    return int(round(p["good_win_pct"] * gg / 100))


def _evil_wins(p: dict) -> int:
    eg = p.get("evil_games") or 0
    if not eg or p.get("evil_win_pct") is None:
        return 0
    return int(round(p["evil_win_pct"] * eg / 100))


def _blank(name: str) -> dict:
    return {
        "name": name,
        "games": 0,
        "wins": 0,
        "losses": 0,
        "win_pct": 0.0,
        "good_games": 0,
        "good_win_pct": None,
        "evil_games": 0,
        "evil_win_pct": None,
    }


def _finalize(p: dict, good_wins: int, evil_wins: int) -> dict:
    g, w = p["games"], p["wins"]
    gg, eg = p["good_games"], p["evil_games"]
    return {
        "name": p["name"],
        "games": g,
        "wins": w,
        "losses": g - w,
        "win_pct": round(100.0 * w / g, 1) if g else 0.0,
        "good_games": gg,
        "good_win_pct": round(100.0 * good_wins / gg, 1) if gg else None,
        "evil_games": eg,
        "evil_win_pct": round(100.0 * evil_wins / eg, 1) if eg else None,
    }


def apply_three_games(path: str = DEFAULT_JSON) -> None:
    with open(path, encoding="utf-8-sig") as fh:
        payload = json.load(fh)

    by_name = {p["name"]: dict(p) for p in payload["players"]}
    good_wins = {n: _good_wins(p) for n, p in by_name.items()}
    evil_wins = {n: _evil_wins(p) for n, p in by_name.items()}

    for game in THREE_GAMES:
        for name, alignment, won in game:
            if name not in by_name:
                by_name[name] = _blank(name)
                good_wins[name] = 0
                evil_wins[name] = 0
            p = by_name[name]
            p["games"] += 1
            if won:
                p["wins"] += 1
            if alignment == "good":
                p["good_games"] += 1
                if won:
                    good_wins[name] += 1
            else:
                p["evil_games"] += 1
                if won:
                    evil_wins[name] += 1

    players = [
        _finalize(by_name[n], good_wins[n], evil_wins[n]) for n in by_name
    ]
    players.sort(key=lambda x: (-x["win_pct"], -x["games"], x["name"].lower()))

    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"players": players}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"Updated {path} ({len(players)} players)")


if __name__ == "__main__":
    apply_three_games()
