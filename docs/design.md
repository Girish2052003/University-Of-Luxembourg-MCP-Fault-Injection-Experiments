# Design notes

The proxy has one job: change selected MCP calls in a controlled way while leaving the other messages alone. It uses local standard input and output pipes, so the demo can run on a laptop without a web service, model or API account. The [README diagram](../README.md#architecture) shows the processes and data flow.

## How a call moves through the proxy

The client sends a request. The proxy reads a copy to identify its request ID and tool name, chooses whether the rule applies, and forwards the request. Request corruption changes the configured argument at this point.

When the server replies, the proxy uses the request ID to find the original call. A selected response can be delayed, replaced with a tool error, given a wrong fact, or have a fact removed. If the result does not match the supported structure, it is forwarded unchanged and the reason is logged.

Normal messages keep their original bytes. Parsing a copy avoids unnecessary changes to formatting, IDs or metadata. The client and server use the official MCP SDK 2.3.0, with protocol 2026-07-28 selected in the demo.

## Where the work lives

| File | Responsibility |
| --- | --- |
| `policy.py` | Validate the JSON rule and choose target calls |
| `injectors.py` | Make a changed copy of a supported request or result |
| `proxy.py` | Forward messages, match replies to requests and manage delayed replies |
| `evidence.py` | Write each event to a separate JSONL file |
| `toy_server.py` | Serve fictional pages and evaluate bounded arithmetic |
| `demo.py` | Run the conditions and check the answers against known values |

One proxy wraps one server process. The demo puts all three tools in that server to keep the example small. The proxy can wrap another local stdio server using the same command interface.

## Why these choices

**Choose calls before replies arrive.** The rule uses a SHA-256 value derived from the configuration, seed, tool and received target-call number. Two runs with the same ordered calls make the same choices even if their replies arrive in different orders. A probability controls selection; it does not set an exact quota for a short run.

**Keep one rule per run.** A single active fault makes its effect easier to trace. The five mechanisms cover late replies, visible errors, wrong facts, changed inputs and missing facts. Combined faults would need a separate policy for ordering and interpreting their effects.

**Preserve the result structure.** The SDK validates candidate tool results. Text changes update both the structured result and its JSON text copy. Omission removes a sentence from `page_text`, leaving the result's required fields in place.

**Handle waiting and cancellation separately.** A delayed reply gets its own asynchronous task, allowing other replies through. Cancellation releases its active request slot immediately and cancels a held reply. Client EOF cancels holds before the proxy waits for the server to stop. Writes are serialized so two replies cannot mix their bytes.

**Record the change before sending it.** Each applied fault has a log entry with its request, rule, change and message hashes. A failed evidence write stops the run. Application and delivery are separate events because a connection can fail after the change is made.

**Check the facts as well as the arithmetic.** The demo's known figures are 100 and 120, giving 20% growth. Changing 120 to 150 produces 50%. The calculator works, but the final answer is wrong. The checker compares both the source figures and the result, after the workflow has used only tool observations.

## Scope

The error fault replaces a reply after the tool has executed; it cannot undo side effects. The demo tools have no external side effects. The proxy does not add retries, repair answers, intercept internal agent messages, or run a three-agent system.

Supported transports, result shapes, resource bounds and untested platforms are listed in the [README limits](../README.md#limits). The [verification record](verification.md) gives the executed tests and measured results.
