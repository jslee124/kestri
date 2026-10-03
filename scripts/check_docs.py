"""Check bilingual Markdown pairing, local links, and engineering identifiers."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIERS = re.compile(r"\b(?:[A-Z]+-\d{3}|AC-\d{2}|ADR-\d{4}|M[0-4])\b")
LINKS = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def main() -> int:
    paths = (
        sorted(ROOT.glob("README*.md"))
        + sorted((ROOT / "docs").rglob("*.md"))
        + sorted((ROOT / "design").rglob("*.md"))
    )
    errors: list[str] = []
    for path in paths:
        content = path.read_text(encoding="utf-8")
        chinese = path.name.endswith(".zh-CN.md")
        other = path.with_name(
            path.name.replace(".zh-CN.md", ".md") if chinese else f"{path.stem}.zh-CN.md"
        )
        if not other.is_file():
            errors.append(f"{path.relative_to(ROOT)}: missing translation")
            continue
        if f"]({other.name})" not in content:
            errors.append(f"{path.relative_to(ROOT)}: missing language link")
        if not chinese:
            translated = other.read_text(encoding="utf-8")
            if set(IDENTIFIERS.findall(content)) != set(IDENTIFIERS.findall(translated)):
                errors.append(f"{path.relative_to(ROOT)}: engineering identifiers differ")
            if len(re.findall(r"^#+ ", content, re.M)) != len(
                re.findall(r"^#+ ", translated, re.M)
            ):
                errors.append(f"{path.relative_to(ROOT)}: heading counts differ")
        for link in LINKS.findall(content):
            target = link.split("#", 1)[0]
            if not target or ":" in target:
                continue
            if not (path.parent / target).is_file():
                errors.append(f"{path.relative_to(ROOT)}: missing link target {target}")
    for error in errors:
        print(error)
    if errors:
        return 1
    print(f"PASS: {len(paths)} documents; translations, local links, and identifiers checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
