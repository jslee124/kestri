"""Keep packaged migrations readable without depending on a system SQL formatter."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src/kestri/storage/sql"


def main() -> int:
    errors = []
    paths = sorted(ROOT.glob("*.sql"))
    for path in paths:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            reason = None
            if "\t" in line:
                reason = "use spaces, not tabs"
            elif len(line) > 100:
                reason = "split long definitions and conditions (maximum 100 columns)"
            elif (len(line) - len(line.lstrip())) % 4:
                reason = "indent with multiples of four spaces"
            if reason:
                errors.append(f"{path.name}:{number}: {reason}")
    for error in errors:
        print(error)
    if errors:
        return 1
    print(f"PASS: {len(paths)} SQL migrations; indentation and line width checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
