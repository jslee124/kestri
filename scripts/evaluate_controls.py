"""Reproducible route-only regression metrics; not a language-model quality claim."""

import json
from pathlib import Path

from kestri.assistant.routing import route


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "tests/assistant/routes.json").read_text())
    matches = 0
    counterexamples = 0
    wrong_writes = 0
    for case in cases:
        selected = route(case["text"], direct=True, reply=False, state=None)
        matches += (selected.command, selected.kind) == (case["command"], case["kind"])
        if case["command"] is None and case["kind"] == "foreground":
            counterexamples += 1
            wrong_writes += selected.command in {"new", "stop"} or selected.kind in {
                "task_control",
                "memory_control",
            }
    print(
        json.dumps(
            {
                "scope": "labeled deterministic routing regression; no provider call",
                "cases": len(cases),
                "correct_routes": matches,
                "counterexamples": counterexamples,
                "wrong_mutation_routes": wrong_writes,
                "limits": "Not a measured real-world misunderstanding or mutation rate.",
            },
            indent=2,
        )
    )
    return int(matches != len(cases) or wrong_writes != 0)


if __name__ == "__main__":
    raise SystemExit(main())
