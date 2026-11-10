"""Run seven local conditions plus a repeated deterministic fault schedule."""
import argparse
import asyncio
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import re
import sys
import time

from mcp import Client, StdioServerParameters
from . import __version__

PROTOCOL = "2026-07-28"


def scenario_config(fault: str) -> dict:
    parameters = {
        "latency": {"delay_ms": 200},
        "error": {"message": "Synthetic upstream service unavailable"},
        "semantic": {"old": "Revenue FY2025: EUR 120 million.", "new": "Revenue FY2025: EUR 150 million."},
        "request": {"argument": "url", "old": "fixture://acme/2025", "new": "fixture://acme/2024"},
        "omission": {"old": "Revenue FY2025: EUR 120 million.\n"},
    }
    active = "semantic" if fault == "disabled" else fault
    return {"enabled": fault != "disabled", "seed": 42, "tool": "fetch_page", "fault": active,
            "probability": 1.0, "occurrence": 1, "parameters": parameters[active]}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def connection(output: Path, condition: str, cfg: dict | None) -> StdioServerParameters:
    args = ["-m", "faultlab.toy_server"]
    if cfg is not None:
        path = output / "configs" / f"{condition}.json"
        write_json(path, cfg)
        args = ["-m", "faultlab.proxy", "--config", str(path), "--log", str(output / f"{condition}.jsonl"),
                "--", sys.executable, *args]
    return StdioServerParameters(command=sys.executable, args=args)


async def workflow(client: Client, trace: list) -> tuple[dict, str]:
    """Produce an answer from observations only. No reference values are consulted."""
    async def invoke(name, arguments):
        start = time.monotonic()
        r = await client.call_tool(name, arguments)
        trace.append({"event": "client_observation", "seq": len(trace) + 1, "tool": name,
                      "arguments": arguments, "elapsed_ms": (time.monotonic()-start)*1000,
                      "is_error": r.is_error, "structured_content": r.structured_content,
                      "text": [x.text for x in r.content if getattr(x, "type", None) == "text"]})
        return r
    hits = await invoke("web_search", {"query": "ACME annual revenue comparison FY2025"})
    data = hits.structured_content
    # The pinned SDK wraps a primitive/list return in a result object.
    if isinstance(data, dict):
        data = data.get("result")
    if hits.is_error or not isinstance(data, list) or not data:
        return {}, "tool_error"
    page = await invoke("fetch_page", {"url": data[0]["url"]})
    if page.is_error:
        return {}, "tool_error"
    body = page.structured_content["page_text"]
    figures = re.findall(r"Revenue FY(\d{4}): EUR ([0-9]+(?:\.[0-9]+)?) million\.", body)
    values = {year: float(value) for year, value in figures}
    if "2024" not in values or "2025" not in values or values["2024"] == 0:
        return {}, "incomplete"
    prior, current = values["2024"], values["2025"]
    calculation = await invoke("calculator", {"expression": f"({current}-{prior})/{prior}*100"})
    if calculation.is_error:
        return {}, "tool_error"
    return {"prior": prior, "current": current, "growth_percent": calculation.structured_content["result"]}, "completed"


def assess(report: dict, status: str) -> dict:
    """Independent frozen answer sheet, outside the observation-consuming workflow."""
    expected = {"prior": 100.0, "current": 120.0, "growth_percent": 20.0}
    complete = status == "completed"
    correct = complete and all(type(report.get(k)) in (int, float) and
                              math.isclose(report[k], v, abs_tol=1e-9, rel_tol=0) for k, v in expected.items())
    return {"workflow_completed": complete, "verified_correct": correct,
            "assessment": "correct_report" if correct else "wrong_completed_report" if complete else status,
            "growth_percent": report.get("growth_percent"), "observed_report": report,
            "expected_report": expected}


async def condition_run(output, condition):
    cfg = None if condition == "direct" else scenario_config(condition)
    trace = []
    async with Client(connection(output, condition, cfg), mode=PROTOCOL, read_timeout_seconds=5) as client:
        await client.list_tools()
        start = time.monotonic()
        report, status = await workflow(client, trace)
        elapsed = (time.monotonic() - start) * 1000
    (output / f"{condition}.observations.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in trace), encoding="utf-8")
    return {"condition": condition, **assess(report, status), "workflow_ms": elapsed,
            "tool_calls": len(trace), "model_tokens": 0}


async def replay_run(output):
    cfg = {**scenario_config("semantic"), "occurrence": None, "probability": 0.4}
    schedules = []
    for label in ["replay_a", "replay_b"]:
        async with Client(connection(output, label, cfg), mode=PROTOCOL, read_timeout_seconds=5) as client:
            await client.list_tools()
            for _ in range(20):
                await client.call_tool("fetch_page", {"url": "fixture://acme/2025"})
        rows = [json.loads(x) for x in (output / f"{label}.jsonl").read_text().splitlines()]
        schedules.append([{k: row[k] for k in ("ordinal", "selected", "draw")} for row in rows if row["event"] == "decision"])
    return {"same_decisions": schedules[0] == schedules[1], "calls_per_run": 20,
            "selected_count": sum(row["selected"] for row in schedules[0]), "schedule": schedules[0],
            "scope": "same config and ordered target calls; timestamps, process IDs and wall-clock latency excluded"}


async def demonstrate(output):
    output.mkdir(parents=True, exist_ok=False)
    (output / "configs").mkdir()
    results = []
    for name in ["direct", "disabled", "latency", "error", "semantic", "request", "omission"]:
        results.append(await condition_run(output, name))
    replay = await replay_run(output)
    summary = {"data": "synthetic; no LLM and no real-company claims", "conditions": results, "replay": replay}
    write_json(output / "summary.json", summary)
    write_json(output / "environment.json", {"python": platform.python_version(), "platform": platform.system(),
                "mcp": version("mcp"), "faultlab": __version__, "protocol": PROTOCOL,
                "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))}})
    lines = ["# Measured local demonstration", "", "Synthetic fixtures; no LLM/API calls. Each row is one execution, not a statistical benchmark.", "",
             "| Condition | Workflow completed | Independently correct | Growth (%) | Workflow ms | Tool calls |",
             "| --- | --- | --- | --- | --- | --- |"]
    for r in results:
        lines.append(f"| {r['condition']} | {r['workflow_completed']} | {r['verified_correct']} | {r['growth_percent']} | {r['workflow_ms']:.2f} | {r['tool_calls']} |")
    lines += ["", f"Replay: {replay['selected_count']} selected calls out of 20 at configured p=0.4; two runs give identical decisions: {replay['same_decisions']}.",
              "", "The semantic fault completes the workflow but fails the independent answer check. Error, wrong-year request and omitted fact prevent completion in this deterministic client. This does not measure an LLM's recovery behaviour.",
              "", "Read summary.json for full outcomes; *.observations.jsonl are client observations; the other JSONL files are proxy intervention logs. environment.json binds the run to source hashes."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not replay["same_decisions"]:
        raise RuntimeError("deterministic schedule replay failed")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("local-evidence"), help="new directory; existing evidence is not overwritten")
    args = parser.parse_args()
    try:
        summary = asyncio.run(demonstrate(args.output.resolve()))
    except FileExistsError:
        print("Output directory already exists; choose a new --output path to preserve evidence.", file=sys.stderr)
        return 1
    for r in summary["conditions"]:
        print(f"{r['condition']}: {r['assessment']}; growth={r['growth_percent']}; {r['workflow_ms']:.2f}ms")
    print(f"Reproducible schedule: {summary['replay']['same_decisions']}")
    print(f"Evidence: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
