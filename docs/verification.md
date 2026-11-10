# Verification record

Verified on **10 November 2026**, using Linux, Python **3.12.14**, official MCP SDK **2.3.0**, protocol **2026-07-28**, and pytest **9.2.0**. This record describes executed checks, not proposed results.

## Clean installation

The fixed source was exported from Git into a separate directory. A new virtual environment was created and the README's installation commands were executed:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m pip check
python -m pytest -q
```

The verification environment used an absolute virtual-environment path outside the exported source directory; this is equivalent to activation above. Dependency checking reported **No broken requirements found.** The full suite reported **58 passed in 34.07s**. The captured pytest output is retained in [evidence/tests.txt](../evidence/tests.txt).

| Test group | Cases | What it establishes |
| --- | ---: | --- |
| Core | 32 | Configuration validation, deterministic decisions, target isolation, transformations and evidence records |
| SDK and process integration | 14 | Real MCP operation, five faults, raw forwarding, typed IDs, concurrent replies, timeouts, cancellation and process shutdown |
| Demonstration and independent checker | 3 | Seven conditions, actual injection logs, reproducible schedule and rejection of incorrect completed reports |
| Review regressions | 9 | Malformed results skipped, cancellation capacity released, task-start cancellation race handled and failed evidence writes prevent changed-response delivery |

## Review findings resolved

A separate code review identified three concrete defects in the initial implementation. Each was reproduced in a failing regression before being fixed:

- Cancelled requests retained active slots when the server sent no reply. Cancellation now releases capacity immediately and retains bounded recent-cancellation records. A related task-start race is covered, including protection against old callbacks removing new request state.
- Malformed complete results could be counted as applied latency/error faults. The pinned SDK now validates candidate results before transformation; malformed candidates are skipped.
- Held replies could be delivered while the upstream drained after client EOF. EOF now cancels holds immediately, before waiting for upstream shutdown, and new holds are prevented during that shutdown.

The reviewer reported no additional material blocker in the reviewed scope. The subsequent fixed source passed the full development and clean-install suites; the final diff was not independently re-reviewed.

## Measured evidence and limits

The standalone demo was run from the clean installation. [REPORT.md](../evidence/REPORT.md) contains measured outcomes, [summary.json](../evidence/summary.json) contains the independent verdicts, and [environment.json](../evidence/environment.json) records source SHA-256 hashes and versions. The source hashes were checked against the files included in the final repository tree.

Baseline and disabled-proxy conditions produce the independently correct 20% growth. Semantic corruption produces a completed 50% answer that the independent checker rejects. Error, wrong-year request and missing-fact conditions prevent completion. Two separately started 20-call runs produce the same decision sequence. These are controlled demonstrations, not estimated failure rates for LLM agents.

Native Windows, macOS execution, other Python/SDK/protocol versions, HTTP transport, distributed operation and LLM recovery were not verified. The tests are executable evidence for these specific behaviours, not a formal proof or universal protocol conformance claim. The README documents operational bounds and cancellation-history limits.
