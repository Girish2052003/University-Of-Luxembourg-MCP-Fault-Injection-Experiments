# Understanding the implementation

## The three processes

The client asks for tools. The proxy reads the request and normally passes the same bytes on. The server runs the tool and sends a reply. The proxy normally passes that reply back unchanged. Standard input/output are local pipes; MCP does not require an LLM.

## Reading order

1. `toy_server.py`: see the two fixed pages and the arithmetic tool. The figures are fictional.
2. `policy.py`: `Config` rejects invalid settings; `Policy` counts only calls to the selected tool. A stable hash chooses whether each call is selected.
3. `injectors.py`: pure functions return either a changed copy with a description, or a skip reason. They do not alter the original object.
4. `evidence.py`: each event is written as one JSON line with sequence, run and config identity.
5. `proxy.py`: joins those pieces to actual subprocess pipes. A pending table connects request IDs to tool names. Numeric 1 and string "1" remain different keys. Delays run as separate tasks; writes are serialized.
6. `demo.py`: makes real SDK calls, computes an answer from observations, then checks it against an independent answer sheet.

## Questions to be ready to explain

**Why can 50% be wrong if the calculator worked?** The calculator accurately computed growth from 100 to 150. The current-year fact should have been 120. Correct arithmetic cannot repair false input.

**Why is missing data different from an invalid response?** The omission keeps a valid page-text string but removes a fact needed by the task. Structural validity and factual completeness are different checks.

**Why the additional disabled-proxy run?** It checks the proxy itself before attributing a change to the selected fault. Timing overhead can exist even when payloads are untouched.

**What exactly is reproducible?** Which controlled call numbers get selected, and which changes are made. Clocks, process IDs and the call sequence a future LLM chooses are not controlled by a seed in this proxy.

**Why log skipped rules?** A selected rule might not find its expected text. Claiming a fault happened would then be false. Selected, applied and delivered are distinct facts.

**What happens when the client gives up?** Cancellation frees the active request slot immediately. If the proxy is holding that reply, it cancels the delay. A bounded history suppresses recent cancelled replies that arrive late. Closing the client input cancels holds before waiting for the server to stop. Tests cover both real SDK timeouts and immediate cancellation before a delay task has started.

**Does the error mean the tool never executed?** No. This implementation substitutes an error after execution. The demo tools have no external side effects.

**Does the demonstration prove multi-agent reliability?** No. It validates the injector and demonstrates propagation in a deterministic client. A separate experiment is needed for agent robustness.

**What did AI contribute?** Code, tests, debugging and documentation were AI-assisted. The user must understand the final implementation and describe personal contributions accurately.
