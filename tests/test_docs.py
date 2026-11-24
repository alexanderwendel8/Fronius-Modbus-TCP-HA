"""Deutsche und englische Fassung von README und Changelog müssen gleich aufgebaut sein.

Die Inhalte werden nicht verglichen (verschiedene Sprachen), aber ihre Struktur:
Überschriften, Tabellen (Zeilenzahl), Aufzählungspunkte und Codeblöcke je Abschnitt,
im Changelog zusätzlich die Versionsabschnitte. Fehlt in einer Fassung ein Abschnitt,
eine Tabellenzeile oder ein Changelog-Eintrag, schlägt der Test fehl.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PAIRS = [("README.md", "README.en.md"), ("CHANGELOG.md", "CHANGELOG.en.md")]
# Abschnittsnamen, die sich zwischen den Sprachen unterscheiden dürfen, weil Workflows
# sie suchen: "## Unveröffentlicht" (Deutsch) entspricht "## Unreleased" (Englisch).
UNRELEASED = {"Unveröffentlicht": "Unreleased"}

HEADING = re.compile(r"^(#{1,6}) (.*)$")
BULLET = re.compile(r"^\s*(?:[-*]|\d+\.) ")


def _structure(text: str) -> list[tuple]:
    """Gliederung als Liste: je Überschrift (Ebene, Version oder None) und die Blöcke darunter."""
    sections: list[tuple] = []
    level, title = 0, ""
    tables: list[int] = []
    bullets = code = 0
    rows = 0
    in_code = False

    def close() -> None:
        nonlocal rows
        if rows:
            tables.append(rows)
            rows = 0

    def flush() -> None:
        close()
        version = title if re.fullmatch(r"\d+\.\d+\.\d+", title) else None
        sections.append((level, version, tuple(tables), bullets, code))

    for line in text.splitlines():
        if line.startswith("```"):
            close()
            in_code = not in_code
            code += in_code
            continue
        if in_code:
            continue
        if match := HEADING.match(line):
            flush()
            level, title = len(match[1]), match[2].strip()
            tables, bullets, code = [], 0, 0
            continue
        if line.startswith("|"):
            rows += 1
            continue
        close()
        if BULLET.match(line):
            bullets += 1
    flush()
    return sections


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(("german", "english"), PAIRS)
def test_language_versions_have_same_structure(german: str, english: str) -> None:
    de, en = _structure(_read(german)), _structure(_read(english))
    assert len(de) == len(en), f"{german}: {len(de)} Abschnitte, {english}: {len(en)}"
    for index, (a, b) in enumerate(zip(de, en, strict=True)):
        assert a == b, f"Abschnitt {index} unterscheidet sich: {german} {a} / {english} {b}"


@pytest.mark.parametrize(("german", "english"), PAIRS)
def test_language_versions_link_each_other(german: str, english: str) -> None:
    assert f"]({english})" in _read(german).splitlines()[0]
    assert f"]({german})" in _read(english).splitlines()[0]


def test_changelog_versions_match() -> None:
    def versions(name: str) -> list[str]:
        return [
            UNRELEASED.get(line[3:].strip(), line[3:].strip())
            for line in _read(name).splitlines()
            if line.startswith("## ")
        ]

    assert versions("CHANGELOG.md") == versions("CHANGELOG.en.md")
