# M0 validation record

[简体中文](m0-validation.zh-CN.md) · [Documentation](../README.md)

Validation date: 2026-10-01. Status: M0 verified within the scope below.

## Revision and environment

Implementation revision: [`84a727b`](https://github.com/jslee124/kestri/commit/84a727b28c57dc0888753c7a104eb359474105e4). The documents-only baseline is `e07e2d4`.

Implementation fingerprint (SHA-256): `212b31a71cf466ed3f4a23544ae16baa9e401c68f7782b3d0aaa9a670ec0dfe8`. Compute it by concatenating each path, a NUL byte, its file bytes, and another NUL byte, for sorted `src/kestri/*.py`, followed by `pyproject.toml` and `uv.lock`. This identifies the implementation used for the live checks independently of later documentation changes.

Local environment: macOS, arm64, CPython 3.14.7, uv 0.12.3. Locked integration versions: LangChain 1.4.3, langchain-deepseek 1.1.1, LangGraph 1.2.12. The project baseline is Python 3.14; dependency installation succeeded on this interpreter.

## Controlled checks

| Check | Observed result |
| --- | --- |
| Ruff lint and formatting | Passed |
| Strict mypy on application source | Passed |
| pytest | 18 passed; offline, no provider credentials required |
| Bilingual/local-link/identifier check | Passed; see `scripts/check_docs.py` for its limited scope |
| Source distribution and wheel build | Passed locally with `uv build` |

The tests execute the real framework loop and SDK request serialization over mocked HTTP. They cover two-turn continuity, reasoning replay across tool calls and turns, empty assistant tool-call content, strict tool inputs, known tool errors, provider authentication failure, model/tool limits, deadline cancellation, explicit cancellation, configured endpoint, and secret-free evidence. A session cannot continue after failure or interruption. Provider error bodies are suppressed.

The [CI workflow](../../.github/workflows/checks.yml) also passed on Linux with Python 3.14 for implementation revision `84a727b`: [run 36834367301](https://github.com/jslee124/kestri/actions/runs/36834367301). It completed the same offline checks and package build, without live provider calls.

## Live DeepSeek evidence

| Mode | Evidence | Observed result |
| --- | --- | --- |
| `disabled` | [Non-thinking record](evidence/m0-disabled.json) | Two verified turns, four model responses, successful tool results 42 and 50 |
| `enabled` | [Thinking record](evidence/m0-enabled.json) | Two verified turns, four model responses, successful tool results 42 and 50 |

Both checks used `deepseek-flash` at the official endpoint, with the recorded limits and zero SDK retries. The model requested `checked_add`, received its real result, answered, and then added 8 to the previous result. Usage metadata, mode, versions, and timings are retained; no precise billing is claimed.

Not every response in the thinking-mode run contained reasoning. The record includes booleans indicating which did. Outbound replay is separately verified by the payload-level regression test. Reasoning text stays in process-local agent state and is excluded from published evidence. The compatibility adapter isolates a private SDK hook; dependency upgrades must rerun that regression and live checks.

## Traceability and limits

This verifies the [M0 exit criteria](milestones.md) and foundations for CHAT-001, SEC-001, OPS-001, and OPS-002, including only the model/tool portions of AC-12. No full first-version acceptance case is closed.

M0 has no Telegram, web retrieval, PostgreSQL, scheduled tasks, personal memory, automatic compression, input-token budgeting, monthly spending enforcement, workspace access, or Docker isolation. LangGraph checkpoints are ephemeral. Failure and limit evidence is controlled/offline; the live runs validate the successful provider path. These checks do not establish long-term reliability, general reasoning quality, deployment safety, or a personal-use trial.

The next target is M1, the first Telegram research workflow. See [milestones](milestones.md) for its additional authorization, persistence, tool-boundary, and recovery gates.
