#!/usr/bin/env python3
"""Build a concise 2026 Worlds calendar from the upstream iCalendar feed."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import urllib.request
from collections import defaultdict
from pathlib import Path


SOURCE = (
    "https://zlypher.github.io/lol-events/cal/"
    "league-of-legends-world-championship.ical"
)
YEAR = "2026"
CALENDAR_NAME = "LOL世界赛"


def unfold(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def read_events(lines: list[str]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    event: dict[str, str] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            event = {}
        elif line == "END:VEVENT":
            if event is not None and event.get("DTSTART", "").startswith(YEAR):
                events.append(event)
            event = None
        elif event is not None and ":" in line:
            key, value = line.split(":", 1)
            event[key] = value
    return sorted(events, key=lambda event: (event.get("DTSTART", ""), event.get("UID", "")))


def simple_title(original: str, counters: dict[str, int]) -> str:
    match = re.fullmatch(r"\(([^)]+)\)\s*([^:]+):\s*(.+)", original)
    if not match:
        return original
    stage, round_name, teams = match.groups()
    if not re.search(r"\b(?:TBD|TBC)\b", teams, flags=re.IGNORECASE):
        return teams
    if not re.fullmatch(r"\s*(?:TBD|TBC)\s+vs\s+(?:TBD|TBC)\s*", teams, re.I):
        return re.sub(r"\b(?:TBD|TBC)\b", "待定", teams, flags=re.I)

    key = f"{stage}|{round_name}"
    counters[key] += 1
    number = counters[key]
    if stage == "Group Stage":
        round_number = re.search(r"Round\s+(\d+)", round_name, re.I)
        if round_number:
            return f"瑞士轮第{round_number.group(1)}轮 第{number}场"
        return f"瑞士轮 第{number}场"
    if stage == "Play-In":
        return f"入围赛 第{number}场"
    if stage == "Playoffs":
        if re.search("Quarterfinal", round_name, re.I):
            return f"八强赛 第{number}场"
        if re.search("Semifinal", round_name, re.I):
            return f"四强赛 第{number}场"
        if re.search("Grand Final", round_name, re.I):
            return "决赛"
    return f"对阵待定 第{number}场"


def fold(line: str) -> list[str]:
    result: list[str] = []
    current = ""
    for char in line:
        limit = 75 if not result else 74
        if current and len((current + char).encode("utf-8")) > limit:
            result.append(current)
            current = char
        else:
            current += char
    result.append(current)
    return [result[0], *(f" {part}" for part in result[1:])]


def render(events: list[dict[str, str]]) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LOL Worlds Simple Calendar//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"NAME:{CALENDAR_NAME}",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    counters: dict[str, int] = defaultdict(int)
    fallback_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for event in events:
        for required in ("UID", "DTSTART", "DTEND", "SUMMARY"):
            if not event.get(required):
                raise ValueError(f"Event missing {required}: {event!r}")
        lines.append("BEGIN:VEVENT")
        for key in ("UID", "SEQUENCE", "DTSTAMP", "DTSTART", "DTEND", "STATUS"):
            if key in event:
                lines.append(f"{key}:{event[key]}")
            elif key == "DTSTAMP":
                lines.append(f"DTSTAMP:{fallback_stamp}")
        lines.append(f"SUMMARY:{simple_title(event['SUMMARY'], counters)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    physical = [part for line in lines for part in fold(line)]
    return ("\r\n".join(physical) + "\r\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("site/worlds.ics"))
    args = parser.parse_args()
    request = urllib.request.Request(
        SOURCE, headers={"User-Agent": "LOL-Worlds-Simple-Calendar/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        source = response.read().decode("utf-8-sig")
    events = read_events(unfold(source))
    if not events:
        raise ValueError("Upstream calendar contains no 2026 Worlds events")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(render(events))
    print(f"Wrote {len(events)} events to {args.output}")


if __name__ == "__main__":
    main()

