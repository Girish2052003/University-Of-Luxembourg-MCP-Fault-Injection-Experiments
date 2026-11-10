# MCP-FaultLab Implementation Plan

**Goal:** Deliver a runnable, verified Part 2 prototype with five mechanisms and measured evidence.
**Architecture:** Raw stdio forwarding; official SDK endpoints; pure deterministic policy/transforms; separate JSONL evidence and external correctness checks.
**Tech stack:** Python 3.11+, MCP 2.3.0, pytest 9.2.0.
**Spec:** [design.md](design.md).

## Global constraints
No model/API cost. Protocol 2026-07-28. Untouched bytes preserved. No private assignment files. All five mechanisms, test evidence, README, clean-install verification. Approved for continuous implementation.

## Review focus
Malformed or unsupported result shapes must not produce fake applied events; cancellation must suppress held replies; duplicate numeric/string IDs must not be conflated; evidence failures must stop injection; errors/EOF must not leave child processes running. Tests below own these behaviours.

## Task 1: Configuration, policy, transformations and evidence
Files: src/faultlab/{policy,injectors,evidence}.py; tests/test_core.py.
Interfaces: Config.from_dict(dict); Policy.decide(tool)->Decision|None; transform_request/transform_response(dict,Config)->(dict|None,detail); Evidence.emit(event,**fields).
- [x] Write behavioural tests for invalid configs, p0/p1, deterministic intermediate probability and tool isolation, transformations preserving IDs/schema/content copies, skipped shapes, evidence sequencing/digests.
- [x] Run pytest tests/test_core.py; confirm missing implementation failures.
- [x] Implement pure core and logger; rerun until all pass; commit.

## Task 2: Real MCP server and transparent async proxy
Files: src/faultlab/{toy_server,proxy}.py; tests/test_integration.py; tests/wire_server.py; tests/test_regressions.py.
Interfaces: python -m faultlab.toy_server; python -m faultlab.proxy --config PATH --log PATH -- COMMAND [ARGS].
- [x] Write SDK integration tests for baseline/list/call, five mechanisms, raw forwarding, subsequent success after error; real-process tests for out-of-order responses, concurrent latency, cancellation, EOF and child failure.
- [x] Run tests before implementation; confirm subprocess/feature failures.
- [x] Implement bounded forwarding and lifecycle management; verify all tests; commit.

## Task 3: Reproducible demonstration, packaging and documentation
Files: src/faultlab/demo.py; config/*.json; tests/test_demo.py; README.md; docs/{requirements,verification,ai-use}.md; evidence/*.
Interface: python -m faultlab.demo --output local-evidence; python -m pytest -q.
- [x] Write subprocess demo test for direct/disabled/five conditions, independent correctness, actual injection evidence and reproducible decisions; confirm missing module.
- [x] Implement demo, run and retain actual logs; document one command per entry point and precise limitations.
- [x] Lock dependencies, run tests/demo from a clean environment and create a clean package; final independent code review and verified fixes.
- [ ] Publish original implementation and evidence to the supplied repository, verify remote contents, link ready package.
