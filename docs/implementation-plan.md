# Implementation notes

MCP-FaultLab was built in three stages: the fault rules, the real MCP connection, and the demo with its checks. Python keeps the example small, while the official SDK provides the client and server used to test it.

## 1. Rules, changes and logs

`Config.from_dict` checks the configuration before the server starts. `Policy.decide` counts calls to the selected tool and chooses which ones receive a fault. The transformation functions return a changed copy or a reason for skipping the change.

`Evidence.emit` writes one JSON event at a time. Every event carries the run and configuration identity. Existing log files are protected from overwriting.

The core tests cover invalid settings, probabilities 0 and 1, repeated selection sequences, tool targeting, preserved result fields and log contents.

## 2. The client, proxy and server

The proxy connects a client to a server through local pipes. It keeps numeric and string request IDs separate, forwards normal messages unchanged, and delays selected replies without blocking other traffic.

The server supplies `web_search`, `fetch_page` and `calculator`. Test pages are local and fictional. The calculator accepts a small set of arithmetic operations and never uses Python `eval`.

Integration tests exercise all five faults through the official SDK. Additional process tests check unchanged bytes, concurrent replies, cancellation, client timeouts, invalid startup settings and server failure.

## 3. Demonstration and delivery

The demo runs a direct baseline, a disabled proxy and each of the five faults. A separate correctness check compares the observed figures and calculated growth with the reference values. Two restarted runs also compare the fault decisions for the same 20 calls.

The package includes the source, JSON configurations, tests, installation instructions, design notes, known limitations and measured logs. Dependencies are pinned in `requirements.lock`. A fresh installation passed all 58 tests and ran the standalone demo.

The [verification record](verification.md) describes the review fixes and executed checks. [Part 2 coverage](requirements.md) maps the deliverables to their implementation and evidence. [Tools used](tools.md) records the coding assistance.
