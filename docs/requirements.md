# Part 2 coverage

Checked on **10 November 2026** against the supplied Part 2 Option A brief and recruitment email. All required Part 2 items are covered by the implementation and saved evidence below. This page summarises the project's coverage; the university's documents are not included in the repository.

## Required behaviour and files

| Item | Status | Implementation and evidence |
| --- | --- | --- |
| A working MCP client–proxy–server connection | Complete | Official SDK client and server with the proxy between them; SDK integration tests |
| Normal traffic passes through unchanged | Complete | Original bytes are forwarded when no change applies; raw-message comparison and disabled-proxy demo |
| Added latency | Complete | A selected reply is held asynchronously; SDK timing check, concurrent-reply test and [latency log](../evidence/latency.jsonl) |
| An error response | Complete | A valid tool result with `isError: true`; SDK checks and [error log](../evidence/error.jsonl) |
| A plausible wrong result that still looks successful | Complete | Revenue changes from 120 to 150 while the result remains successful; [semantic log](../evidence/semantic.jsonl) and independently rejected 50% answer |
| Configurable tool, fault and frequency | Complete | JSON settings for tool, mechanism, probability and optional call number; configuration and targeting tests |
| Reproducible fault decisions | Complete | Same configuration and ordered calls produce the same decisions; unit replay and two separate 20-call runs |
| Every injected fault is logged | Complete | JSONL records are written before changed messages are sent; fault-count checks and a failed-write regression |
| Demonstration with a simple MCP server | Complete | Local SDK server with three tools; direct baseline and all five fault conditions |
| Repository or ZIP package | Complete | Versioned source, tests, configurations and evidence in this repository |
| README with running steps, choices and limitations | Complete | [README](../README.md), [design](design.md) and [verification](verification.md) |
| A short demo log showing each fault | Complete | [Measured report](../evidence/REPORT.md), [results](../evidence/summary.json) and a separate JSONL log for each fault |

## Additional features requested for this project

| Feature | Status | Evidence |
| --- | --- | --- |
| Five fault mechanisms | Complete | The three required mechanisms plus request corruption and omission; all exercised through the SDK |
| Request corruption | Complete | A selected URL points to the wrong year; [request log](../evidence/request.jsonl) |
| Incomplete information | Complete | A revenue sentence is removed while result fields remain valid; [omission log](../evidence/omission.jsonl) |
| A clear consequence of wrong tool data | Complete | Correct arithmetic produces the wrong 50% report; the independent checker detects it |
| Automated tests and checked fixes | Complete | 58 tests, including cancellation, timeout, shutdown, malformed results and evidence-write failure |
| Name, architecture and readable explanations | Complete | Author named in the README, architecture diagram, design notes and [walkthrough](walkthrough.md) |
| Coding assistance disclosed | Complete | Short statement and tool list in [tools.md](tools.md) |
| Local execution without paid resources | Complete | Fictional local pages, safe arithmetic, no model API or credentials |

## What this package establishes

The prototype meets the Part 2 Option A requirements. Its repeatability claim assumes the same configuration and ordered requests; it does not promise identical timing or control an LLM's choices. A full agent system, separate web/math deployments and live web sources are unnecessary for this small proxy demonstration.

Part 1, Part 3 and the final written PDF are separate deliverables. The repository supplies the Part 2 code, results and tools statement to accompany that PDF. Passing these tests establishes the listed behaviours in the tested environment; it does not predict an assessment outcome.
