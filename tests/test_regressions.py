import asyncio
import json
from types import SimpleNamespace

import pytest
from faultlab.evidence import Evidence
from faultlab.injectors import transform_response
from faultlab.policy import Config, canonical
from faultlab.proxy import Proxy, MAX_IN_FLIGHT
from tests.test_core import config, response


class Sink:
    """Minimal in-memory byte transport, not a replacement for proxy behaviour."""
    def __init__(self):
        self.data = bytearray()

    def write(self, raw):
        self.data.extend(raw)

    async def drain(self):
        pass


@pytest.mark.parametrize("fault", ["latency", "error"])
@pytest.mark.parametrize("bad_content", [None, "not a list", [{"type": "text", "text": 12}]])
def test_malformed_complete_result_is_not_counted_as_injection(fault, bad_content):
    msg = response()
    if bad_content is None:
        del msg["result"]["content"]
    else:
        msg["result"]["content"] = bad_content
    modified, detail = transform_response(msg, Config.from_dict(config(fault)))
    assert modified is None and detail["reason"]


def test_cancelled_calls_release_capacity_when_server_sends_no_reply(tmp_path):
    async def check():
        cfg = Config.from_dict(config("latency"))
        with Evidence(tmp_path / "events.jsonl", cfg) as log:
            upstream, output = Sink(), Sink()
            proxy = Proxy(cfg, log, SimpleNamespace(stdin=upstream), output)
            for i in range(MAX_IN_FLIGHT + 1):
                await proxy.from_client(canonical({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                    "params": {"name": "fetch_page", "arguments": {}}}) + b"\n")
                await proxy.from_client(canonical({"jsonrpc": "2.0", "method": "notifications/cancelled",
                    "params": {"requestId": i}}) + b"\n")
            assert not proxy.pending
            assert len(proxy.cancelled) <= MAX_IN_FLIGHT
            late = response()
            late["id"] = MAX_IN_FLIGHT
            await proxy.from_server(canonical(late) + b"\n")
            assert not output.data
    asyncio.run(check())


def test_cancellation_before_task_starts_does_not_erase_reused_id(tmp_path):
    async def check():
        cfg = Config.from_dict(config("latency", parameters={"delay_ms": 100}))
        path = tmp_path / "events.jsonl"
        with Evidence(path, cfg) as log:
            output = Sink()
            proxy = Proxy(cfg, log, SimpleNamespace(stdin=Sink()), output)
            request = canonical({"jsonrpc": "2.0", "id": "1", "method": "tools/call",
                "params": {"name": "fetch_page", "arguments": {}}}) + b"\n"
            reply = canonical(response()) + b"\n"
            await proxy.from_client(request)
            await proxy.from_server(reply)
            await proxy.from_client(canonical({"jsonrpc": "2.0", "method": "notifications/cancelled",
                "params": {"requestId": "1"}}) + b"\n")
            await proxy.from_client(request)
            await proxy.from_server(reply)
            new_state = proxy.pending[("str", "1")]
            new_task = proxy.held[("str", "1")][1]
            await asyncio.sleep(0.01)
            assert proxy.pending[("str", "1")] is new_state
            assert proxy.held[("str", "1")][1] is new_task
            await asyncio.gather(*proxy.delay_tasks, return_exceptions=True)
            assert bytes(output.data) == reply
            assert not proxy.pending
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert sum(r["event"] == "fault_cancelled" for r in rows) == 1
        assert sum(r["event"] == "fault_applied" for r in rows) == 1
    asyncio.run(check())


def test_evidence_write_failure_prevents_transformed_response_delivery(tmp_path):
    async def check():
        cfg = Config.from_dict(config())
        log = Evidence(tmp_path / "events.jsonl", cfg)
        output = Sink()
        proxy = Proxy(cfg, log, SimpleNamespace(stdin=Sink()), output)
        await proxy.from_client(canonical({"jsonrpc": "2.0", "id": "1", "method": "tools/call",
            "params": {"name": "fetch_page", "arguments": {}}}) + b"\n")
        log.close()
        with pytest.raises(ValueError):
            await proxy.from_server(canonical(response()) + b"\n")
        assert not output.data
    asyncio.run(check())
