# MCP-FaultLab design

Build a small real stdio MCP proxy with deterministic configurable interventions and auditable evidence. The implementation is independent of an LLM and does not claim to implement a multi-agent workflow.

Use Python 3.11+, official MCP SDK 2.3.0 and explicit protocol 2026-07-28 in the demo. Client and toy server are real SDK subprocesses. The proxy forwards unmodified JSON-lines byte-for-byte and parses copies for request/result correlation. One upstream process per proxy. Discovery, listing, notifications, metadata, IDs and unmatched traffic pass through. Logs never use protocol stdout.

Five mechanisms: response delay; post-execution tool-error replacement; plausible revenue corruption; valid request URL replacement; deletion of a factual sentence while preserving response schema. Only one active rule per configuration. The three response mechanisms are the core; all five are delivery targets. Changes to structured results and their JSON text copies stay consistent. Unsupported shapes are skipped and logged, never reported as injected.

Config declares tool, mechanism, probability, seed, optional eligible-call number and parameters. Stable SHA-256 selection uses canonical config and per-target-tool request ordinal. Same ordered requests/config yield identical decisions; neither wall-clock timing nor an LLM's calls are promised identical. A probability is not an exact finite-sample quota. Assign decisions on request receipt. No fault combinations.

Delay only the selected response without blocking other traffic. Serialize writes. Forward cancellation and cancel a held response. Clean up children on EOF or failure. Track typed request IDs. Fail closed on invalid configuration or inability to record evidence. No silent unlogged injections.

Evidence records sequence/run/request/tool/rule/config/seed, original and transformed digests, exact toy-data change, requested and observed delay, and applied/skipped/cancelled outcomes. Fault events are distinct from delivery events. Diagnostics, raw transport captures and independent report assessment are separate.

Use local synthetic pages and safe arithmetic. The independent expected growth is 20%; changing 120 to 150 against a prior 100 yields 50%, which must be reported as wrong. Completion and correctness are separate outcomes. Subsequent successful calls establish proxy liveness, not LLM recovery.

Validate actual MCP integration, raw preservation, config rejection, selection replay, tool isolation, five fault outcomes, valid envelopes/schema, logging, concurrent replies, cancellation, EOF and process failures. No arbitrary code evaluation or real network fixtures. Demonstration and tests must run from a clean installation.

The proxy does not add retries, alter the server's business logic, fetch real web pages, intercept framework-only agent messages, support HTTP, establish cryptographic integrity, or prove universal correctness. It can pass through other valid messages, but only the documented tool-result forms are fault targets. An injected tool error is produced after the underlying tool has executed. State that limitation for tools with side effects.

The repository contains original code and documentation only. No third-party assignment, private email or credentials belongs here. Final Part 2 delivery is code, README with choices/limitations, automated tests and actual short demo logs. Other written assignment sections are outside this implementation.
