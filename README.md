# MCP-FaultLab

A small, reproducible **stdio MCP fault-injection proxy**. It sits between an MCP client and an existing server, forwards unaffected messages unchanged, and applies configurable faults to selected tool calls. A real official-SDK client/server demo shows the difference between finishing a workflow and producing a correct answer.

**No LLM, API key, paid service, or network access is used by the demonstrations.** Package installation requires access to Python packages. All company names, pages and figures in the demo are synthetic.

## Run in a few commands

Requirements: **Python 3.11+ on Linux or macOS; use WSL on Windows.** Verification was performed on Linux/Python 3.12. Native Windows console pipes are not supported. The official MCP SDK is pinned to 2.3.0 and the demo explicitly uses protocol 2026-07-28.

From this repository's root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
```

Run the demonstration:

```bash
python -m faultlab.demo --output local-evidence
```

Run the tests:

```bash
python -m pytest -q
```

The output directory must be new. For another run, use `--output local-evidence/run-02`. This preserves earlier evidence instead of overwriting it. No Docker, browser, external web server or account is needed.

The checked-in [measured report](evidence/REPORT.md) and [machine-readable outcomes](evidence/summary.json) show an actual run. [Verification](docs/verification.md) records the tested environment and checks. These are small demonstrations, not LLM robustness measurements.

## What the demonstration does

An actual SDK client calls three actual MCP tools in a subprocess server:

1. `web_search(query)` finds a local fixture URL.
2. `fetch_page(url)` returns a status, headers and page text.
3. `calculator(expression)` computes growth using bounded arithmetic, without Python `eval`.

The clean fixture contains FY2024 revenue 100 and FY2025 revenue 120, giving 20% growth. An independent answer checker knows those fixed reference facts. The workflow itself consumes only the tool observations.

| Condition | Intervention | Expected observable outcome |
| --- | --- | --- |
| Direct | No proxy | 20% growth, independently correct |
| Disabled | Proxy with injection off | 20% growth, independently correct |
| Latency | Hold the first selected reply for 200 ms | Same answer, delayed reply |
| Error | Replace a successful result with a valid tool error | Explicit tool failure; later calls still work |
| Semantic | Change the FY2025 revenue 120 to 150 | Calculation finishes at 50%, independently wrong |
| Request | Replace the FY2025 fixture URL with its FY2024 URL | Requested year is unavailable; client reports incomplete |
| Omission | Remove one required factual sentence from page text | Response remains schema-valid; client reports incomplete |

The demo also repeats 20 calls twice at configured probability 0.4 with seed 42, comparing decision sequences. An observed finite-run fraction need not equal the configured probability. Error/request/omission handling is this deterministic client's behaviour, not evidence about an LLM agent.

## Use the proxy with an MCP client

Configure your MCP host to launch this command (replace `python` with the absolute interpreter in your environment if needed):

```bash
python -m faultlab.proxy \
  --config config/semantic.json \
  --log local-evidence/proxy-run.jsonl \
  -- python -m faultlab.toy_server
```

The log's parent directory must exist and its filename must be new. This command waits for MCP JSON-lines on stdin; it is intended to be launched by an MCP client. The demo does this automatically.

Replace the command after `--` with another local stdio MCP server. It is executed as an argument vector, not a shell command. One proxy instance wraps one server. Latency and error target successful modern tool results; content/request transforms support the documented shapes and exact configured matches below. An unsupported result is forwarded unchanged and a skip reason is recorded.

## Configuration

See [config/](config/). Each file defines **one active rule**; faults are not stacked.

```json
{
  "enabled": true,
  "seed": 42,
  "tool": "fetch_page",
  "fault": "semantic",
  "probability": 1.0,
  "occurrence": 1,
  "parameters": {
    "old": "Revenue FY2025: EUR 120 million.",
    "new": "Revenue FY2025: EUR 150 million."
  }
}
```

| Setting | Meaning |
| --- | --- |
| `enabled` | Boolean. False disables injection. |
| `seed` | Integer used by deterministic SHA-256 selection. |
| `tool` | Exact target tool name. Other tools do not advance its call counter. |
| `fault` | `latency`, `error`, `semantic`, `request`, or `omission`. |
| `probability` | Number from 0 to 1. 0 means never; 1 means always, subject to occurrence and applicability. |
| `occurrence` | A positive target-call number, or `null` to consider every target call. Counts received target calls, including ones later skipped. |
| `parameters` | Exact mechanism-specific parameters from the table below. |

| Fault | Parameters | Applicability |
| --- | --- | --- |
| Latency | `delay_ms`:0..60000 | Successful `resultType: complete` response |
| Error | `message`: non-empty string | Successful `resultType: complete` response |
| Semantic | `old`, `new`: different non-empty strings | Exactly one old span in `structuredContent.page_text`; one consistent JSON text copy |
| Request | `argument`, `old`, `new`: non-empty strings; old != new | Exact original value in `params.arguments[argument]` |
| Omission | `old`: non-empty string | Exactly one old span in page text; one consistent JSON text copy |

Invalid/unknown settings fail before launching the server. Candidate tool results are validated with the pinned SDK before an injection is applied. A selected but inapplicable rule is **skipped**, not silently counted as an injection. Semantic/omission transforms keep required `status`, `headers` and `page_text` fields and update both representations. They do not delete a required schema property.

## Design choices

- **Transparent byte forwarding:** parsed copies are used for routing; unmodified frames retain their original bytes, IDs and metadata. Discovery, listing, notifications, protocol errors and unrelated calls are not rewritten. There is ordinary process/parse/log overhead; unchanged content does not mean zero latency.
- **Deterministic policy:** SHA-256 of the canonical config, seed, tool and received target-call ordinal. Selection happens before a response arrives, so response completion order cannot change decisions. Reproducibility assumes the same ordered request sequence. It does not control an LLM, network timing or timestamps.
- **One delayed reply, not a stalled stream:** asynchronous per-response holds allow unrelated replies through. Client cancellation discards the held reply. EOF and errors clean up the wrapped process.
- **Tool errors, not malformed protocol messages:** the injected result has `isError: true`; JSON-RPC errors are a separate mechanism. The real tool has already executed before this replacement. Do not interpret it as proof that a tool with side effects did nothing.
- **Separate evidence:** protocol stdout contains only MCP traffic. JSONL records go to a specified file; diagnostics go to stderr. Evidence failures stop the run. Exclusive log creation protects previous runs.
- **Independent assessment:** source facts and calculated growth are checked separately from workflow completion. The answer sheet is never used to repair the workflow's observations.

See [design](docs/design.md), [requirements and evidence map](docs/requirements.md) and [code walkthrough](docs/walkthrough.md).

## Read the evidence

`evidence/` contains a checked run; reruns go to your selected output directory.

- `REPORT.md`: compact results for a human reader.
- `summary.json`: completion, independent correctness, observed/reference figures and replay decisions.
- `*.observations.jsonl`: what the deterministic client observed, with call durations; these are not raw wire captures.
- `disabled.jsonl`, `latency.jsonl`, `error.jsonl`, `semantic.jsonl`, `request.jsonl`, `omission.jsonl`: proxy events, including every applied intervention.
- `replay_a.jsonl`, `replay_b.jsonl`: independently restarted runs of the same selection schedule.
- `configs/`: exact configurations used.
- `environment.json`: Python/SDK/protocol versions and hashes of the implementation source files.
- `tests.txt`: captured output from the complete suite in a clean installation.

Each applied intervention includes request ID, tool, ordinal, rule, seed, config hash, direction, exact synthetic-data change and before/after message hashes. Delay records distinguish scheduling, application, cancellation and delivery. Hashes identify content; they are not signatures or tamper-proof storage. An applied record preceding a broken transport does not establish delivery; response delivery has a separate event.

## Limits

- Tested MCP revision 2026-07-28 and SDK 2.3.0; no claim of cross-version conformance. HTTP, authentication, subscriptions/MRTR fault injection and distributed deployment are outside scope. Untargeted traffic is forwarded, not fully validated.
- Tool-result transforms are deliberately narrow. This is not a universal semantic editor for arbitrary schemas or multi-content results. The real SDK client validates its declared output shapes in integration tests.
- One process per server; maximum 4 MiB per line and 1024 in-flight requests. Duplicate active request IDs fail rather than being mis-correlated. Use fresh IDs for new requests. Cancellation releases active capacity immediately; the last 1024 cancelled IDs are retained to discard late replies. A new request using one of those IDs clears its cancellation record, so an upstream late reply after ID reuse cannot be distinguished from the new reply.
- Cancellation/EOF cancels held replies immediately, including while the server drains during shutdown. Abrupt termination or a host/power failure can lose buffered OS writes; JSONL is flushed, not a durable transactional journal.
- No built-in agent retries or automatic repair. The toy client safely stops on obvious errors/missing years but trusts a plausible revenue value. It is not a model, three-agent system, or statistical evaluation.
- Positive examples establish measured behaviours; tests do not constitute formal proof. macOS is a POSIX design target but was not independently tested. On Windows use WSL.

## Tools and authorship

Implementation, tests and documentation were produced with OpenAI Codex assistance and checked through executable tests and real SDK runs. See [AI-use record](docs/ai-use.md). No university-provided assignment PDF, private email, or credentials is included. Review the code and measured evidence before using it in a submission or discussing its design.

## Protocol references

- [Official Python SDK 2.3.0 release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0)
- [MCP 2026-07-28 stdio binding](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio)
- [Tool results and errors](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
- [Python SDK protocol versions](https://py.sdk.modelcontextprotocol.io/protocol-versions/)
