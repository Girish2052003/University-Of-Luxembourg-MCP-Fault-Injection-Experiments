# Measured local demonstration

Synthetic fixtures; no LLM/API calls. Each row is one execution, not a statistical benchmark.

| Condition | Workflow completed | Independently correct | Growth (%) | Workflow ms | Tool calls |
| --- | --- | --- | --- | --- | --- |
| direct | True | True | 20.0 | 45.49 | 3 |
| disabled | True | True | 20.0 | 9.54 | 3 |
| latency | True | True | 20.0 | 212.52 | 3 |
| error | False | False | None | 5.55 | 2 |
| semantic | True | False | 50.0 | 10.92 | 3 |
| request | False | False | None | 7.74 | 2 |
| omission | False | False | None | 7.34 | 2 |

Replay: 11 selected calls out of 20 at configured p=0.4; two runs give identical decisions: True.

The semantic fault completes the workflow but fails the independent answer check. Error, wrong-year request and omitted fact prevent completion in this deterministic client. This does not measure an LLM's recovery behaviour.

Read summary.json for full outcomes; *.observations.jsonl are client observations; the other JSONL files are proxy intervention logs. environment.json binds the run to source hashes.
