import copy
import json
import pytest


def config(fault="semantic", **changes):
    params = {
        "semantic": {"old": "Revenue FY2025: EUR 120 million.", "new": "Revenue FY2025: EUR 150 million."},
        "omission": {"old": "Revenue FY2025: EUR 120 million.\n"},
        "request": {"argument": "url", "old": "fixture://acme/2025", "new": "fixture://acme/2024"},
        "latency": {"delay_ms": 200},
        "error": {"message": "Synthetic upstream service unavailable"},
    }
    return {"enabled": True, "seed": 42, "tool": "fetch_page", "fault": fault,
            "probability": 1.0, "occurrence": None, "parameters": params.get(fault, {}), **changes}


def response():
    data = {"status": 200, "headers": {"content-type": "text/plain"},
            "page_text": "SYNTHETIC report\nRevenue FY2024: EUR 100 million.\nRevenue FY2025: EUR 120 million.\n"}
    return {"jsonrpc": "2.0", "id": "1", "result": {"resultType": "complete", "isError": False,
            "structuredContent": data, "content": [{"type": "text", "text": json.dumps(data)}],
            "_meta": {"keep": "yes"}}}


@pytest.mark.parametrize("change", [
    {"probability": -0.1}, {"probability": 1.1}, {"probability": float("nan")},
    {"probability": True}, {"seed": True}, {"enabled": "false"}, {"occurrence": 0},
    {"occurrence": True}, {"tool": ""}, {"fault": "typo"}, {"extra": 1},
    {"parameters": {"old": "", "new": "x"}}, {"parameters": {"old": "x", "new": "x"}},
])
def test_reject_invalid_config(change):
    from faultlab.policy import Config
    with pytest.raises(ValueError):
        Config.from_dict(config(**change))


@pytest.mark.parametrize("delay", [-1, float("inf"), True, 60001])
def test_reject_invalid_delay(delay):
    from faultlab.policy import Config
    with pytest.raises(ValueError):
        Config.from_dict(config("latency", parameters={"delay_ms": delay}))


def test_probability_boundaries_and_occurrence():
    from faultlab.policy import Config, Policy
    off = Policy(Config.from_dict(config(probability=0)))
    on = Policy(Config.from_dict(config(probability=1, occurrence=2)))
    assert [off.decide("fetch_page").selected for _ in range(4)] == [False]*4
    assert [on.decide("fetch_page").selected for _ in range(4)] == [False, True, False, False]


def test_replay_and_unrelated_tools_do_not_change_schedule():
    from faultlab.policy import Config, Policy
    a, b = (Policy(Config.from_dict(config(probability=0.4))) for _ in range(2))
    left = [a.decide("fetch_page").selected for _ in range(100)]
    right = []
    for _ in range(100):
        assert b.decide("calculator") is None
        right.append(b.decide("fetch_page").selected)
    assert left == right
    assert any(left) and not all(left)
    different = Policy(Config.from_dict(config(probability=0.4, seed=43)))
    assert left != [different.decide("fetch_page").selected for _ in range(100)]


def test_disabled_never_selects():
    from faultlab.policy import Config, Policy
    p = Policy(Config.from_dict(config(enabled=False)))
    assert not p.decide("fetch_page").selected


@pytest.mark.parametrize("fault", ["semantic", "omission"])
def test_content_fault_keeps_both_representations_consistent(fault):
    from faultlab.policy import Config
    from faultlab.injectors import transform_response
    old = response()
    untouched = copy.deepcopy(old)
    new, detail = transform_response(old, Config.from_dict(config(fault)))
    assert old == untouched
    assert new["id"] == "1" and new["result"]["isError"] is False
    assert new["result"]["_meta"] == {"keep": "yes"}
    data = new["result"]["structuredContent"]
    assert set(data) == {"status", "headers", "page_text"}
    assert json.loads(new["result"]["content"][0]["text"]) == data
    assert ("150" in data["page_text"]) if fault == "semantic" else ("FY2025" not in data["page_text"])
    assert detail["old"] != detail["new"]


def test_tool_error_is_valid_result_not_protocol_error():
    from faultlab.policy import Config
    from faultlab.injectors import transform_response
    new, _ = transform_response(response(), Config.from_dict(config("error")))
    assert "error" not in new
    assert new["id"] == "1"
    assert new["result"]["isError"] is True
    assert new["result"]["resultType"] == "complete"
    assert "structuredContent" not in new["result"]
    assert "unavailable" in new["result"]["content"][0]["text"]


@pytest.mark.parametrize("damage", ["existing_error", "wrong_shape", "disagree", "multiple_matches", "protocol_error", "input_required"])
def test_unsupported_results_are_skipped(damage):
    from faultlab.policy import Config
    from faultlab.injectors import transform_response
    msg = response()
    if damage == "existing_error": msg["result"]["isError"] = True
    if damage == "wrong_shape": msg["result"]["structuredContent"] = []
    if damage == "disagree": msg["result"]["content"][0]["text"] = "{}"
    if damage == "multiple_matches":
        msg["result"]["structuredContent"]["page_text"] *= 2
        msg["result"]["content"][0]["text"] = json.dumps(msg["result"]["structuredContent"])
    if damage == "protocol_error": msg = {"id": 1, "error": {"code": -32602}}
    if damage == "input_required": msg["result"]["resultType"] = "input_required"
    new, detail = transform_response(msg, Config.from_dict(config()))
    assert new is None
    assert detail["reason"]


def test_request_changes_only_the_selected_argument():
    from faultlab.policy import Config
    from faultlab.injectors import transform_request
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "fetch_page", "arguments": {"url": "fixture://acme/2025"}, "_meta": {"x": 3}}}
    new, _ = transform_request(msg, Config.from_dict(config("request")))
    assert msg["params"]["arguments"]["url"] == "fixture://acme/2025"
    assert new["params"]["arguments"]["url"] == "fixture://acme/2024"
    assert new["params"]["_meta"] == {"x": 3} and new["id"] == 1


def test_evidence_is_valid_jsonl_with_sequence_and_config_identity(tmp_path):
    from faultlab.evidence import Evidence
    from faultlab.policy import Config
    cfg = Config.from_dict(config())
    with Evidence(tmp_path / "e.jsonl", cfg) as log:
        log.emit("fault_applied", request_id="4", detail={"old": 120, "new": 150})
        log.emit("delivered", request_id="4")
    rows = [json.loads(s) for s in (tmp_path / "e.jsonl").read_text().splitlines()]
    assert [r["seq"] for r in rows] == [1,2]
    assert rows[0]["config_sha256"] == rows[1]["config_sha256"]
    assert len(rows[0]["config_sha256"]) == 64
    assert rows[0]["seed"] == 42 and rows[0]["detail"]["new"] == 150


def test_evidence_open_failure_is_fatal(tmp_path):
    from faultlab.evidence import Evidence
    from faultlab.policy import Config
    with pytest.raises(OSError):
        Evidence(tmp_path, Config.from_dict(config()))
