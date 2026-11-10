import json
from pathlib import Path
import subprocess
import sys


def test_demo_emits_measured_conditions_and_independent_verdicts(tmp_path):
    output = tmp_path / "demo"
    p = subprocess.run([sys.executable, "-m", "faultlab.demo", "--output", str(output)],
                       capture_output=True, text=True, timeout=50)
    assert p.returncode == 0, p.stderr
    summary = json.loads((output / "summary.json").read_text())
    cases = {r["condition"]: r for r in summary["conditions"]}
    assert set(cases) == {"direct", "disabled", "latency", "error", "semantic", "request", "omission"}
    for name in ["direct", "disabled", "latency"]:
        assert cases[name]["workflow_completed"] and cases[name]["verified_correct"]
        assert cases[name]["growth_percent"] == 20.0
    assert cases["semantic"]["workflow_completed"]
    assert not cases["semantic"]["verified_correct"]
    assert cases["semantic"]["growth_percent"] == 50.0
    assert cases["semantic"]["assessment"] == "wrong_completed_report"
    for name in ["error", "request", "omission"]:
        assert not cases[name]["verified_correct"] and not cases[name]["workflow_completed"]
    assert summary["replay"]["same_decisions"] is True
    assert summary["replay"]["calls_per_run"] == 20
    assert 0 < summary["replay"]["selected_count"] < 20
    for name in ["latency", "error", "semantic", "request", "omission"]:
        log = [json.loads(x) for x in (output / f"{name}.jsonl").read_text().splitlines()]
        assert len([x for x in log if x["event"] == "fault_applied"]) == 1
    env = json.loads((output / "environment.json").read_text())
    assert env["mcp"] == "2.3.0" and env["protocol"] == "2026-07-28"
    assert "proxy.py" in env["source_sha256"]
    again = subprocess.run([sys.executable, "-m", "faultlab.demo", "--output", str(output)],
                           capture_output=True, text=True, timeout=5)
    assert again.returncode != 0 and "exists" in again.stderr.lower()


def test_oracle_rejects_wrong_values_even_with_correct_growth():
    from faultlab.demo import assess
    #200->240 is20%, but neither is the frozen expected source fact.
    verdict = assess({"prior": 200.0, "current": 240.0, "growth_percent": 20.0}, "completed")
    assert verdict["verified_correct"] is False


def test_oracle_rejects_wrong_growth_and_incomplete_reports():
    from faultlab.demo import assess
    assert not assess({"prior": 100.0, "current": 120.0, "growth_percent": 50.0}, "completed")["verified_correct"]
    assert not assess({}, "incomplete")["workflow_completed"]
