# Part 2 requirements and evidence

This is an original implementation checklist, not a reproduction of a third-party assignment. Part 1 and personal written answers are not part of this package.

| Behaviour/deliverable | Implementation | Executable check / evidence |
| --- | --- | --- |
| Real client-proxy-server path | Official SDK Client, subprocess proxy and MCPServer | `test_official_sdk_direct_server_baseline`, `test_real_sdk_proxy_faults_and_liveness` |
| Unchanged normal traffic | Raw bytes forwarded, copies parsed | `test_byte_preserving_disabled_proxy_and_protocol_errors`; direct and disabled demo |
| Added latency | Async selected-response hold | SDK latency case; concurrent response test; `latency.jsonl` |
| Valid error response | Successful tool result replaced with isError true | Core error test, SDK error case, `error.jsonl` |
| Plausible wrong successful result | Page revenue span changed with schema intact | Core representation test; SDK semantic case; summary records wrong 50% |
| Tool/fault/frequency configurable | Strict Config and per-tool Policy | Validation, p0/p1, occurrence and tool-isolation tests; saved configs |
| Reproducibility | Stable SHA-256 selection |100-call unit replay and two 20-call real-process replays |
| Every applied fault logged | JSONL Evidence, write-before-send | Core evidence checks; each SDK/demo case requires exactly one applied event |
| Simple real MCP server | Three synthetic tools | Real SDK discovery/list/call tests; safe-calculator negative case |
| Request fault extension | Exact argument replacement | Request unit test, SDK request case, `request.jsonl` |
| Incomplete-data extension | Remove factual sentence, retain response fields | Omission unit/SDK cases, `omission.jsonl` |
| Independent correctness | Frozen answer sheet separate from workflow | Oracle tests reject wrong values and wrong arithmetic; semantic demo |
| Operational checks | Correlated replies, cancellation and bounded shutdown | Concurrent typed-ID, real SDK timeout, repeated cancellation, immediate EOF cancellation, child failure and invalid-startup tests |
| Honest injection accounting | Validate candidates and record evidence before delivery | Malformed-result skip tests and evidence-write-failure regression |
| README and short demo log | README and evidence/REPORT.md | Documented clean-install commands; actual saved outcomes |
| Code package | Versioned repository with pinned dependencies | Clean-install verification recorded in verification.md |

All five mechanisms are implemented. The demonstration contains no paid calls and makes no claims about general LLM robustness. The exact test count and final run details are in [verification.md](verification.md).
