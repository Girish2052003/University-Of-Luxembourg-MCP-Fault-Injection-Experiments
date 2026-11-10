import asyncio
import json
import os
from pathlib import Path
import sys
import time

import pytest
from mcp import Client, StdioServerParameters
from tests.test_core import config


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


def sdk_params(tmp_path, cfg=None):
    args = ["-m", "faultlab.toy_server"]
    if cfg is not None:
        path = tmp_path / "config.json"
        path.write_text(json.dumps(cfg))
        args = ["-m", "faultlab.proxy", "--config", str(path), "--log", str(tmp_path / "log.jsonl"),
                "--", sys.executable, *args]
    return StdioServerParameters(command=sys.executable, args=args)


def test_official_sdk_direct_server_baseline(tmp_path):
    async def check():
        async with Client(sdk_params(tmp_path), mode="2026-07-28") as c:
            tools = await c.list_tools()
            assert {t.name for t in tools.tools} == {"web_search", "fetch_page", "calculator"}
            r = await c.call_tool("fetch_page", {"url": "fixture://acme/2025"})
            assert "120" in r.structured_content["page_text"]
            result = await c.call_tool("calculator", {"expression": "(120-100)/100*100"})
            assert result.structured_content == {"result": 20.0}
            unsafe = await c.call_tool("calculator", {"expression": "__import__('os').getcwd()"})
            assert unsafe.is_error
    run(check())


@pytest.mark.parametrize("fault", ["disabled", "latency", "error", "semantic", "request", "omission"])
def test_real_sdk_proxy_faults_and_liveness(tmp_path, fault):
    cfg = config("semantic" if fault == "disabled" else fault, occurrence=1)
    if fault == "disabled": cfg["enabled"] = False
    async def check():
        async with Client(sdk_params(tmp_path, cfg), mode="2026-07-28") as c:
            await c.list_tools()
            start = time.monotonic()
            r = await c.call_tool("fetch_page", {"url": "fixture://acme/2025"})
            elapsed = time.monotonic() - start
            if fault == "error":
                assert r.is_error
            else:
                assert not r.is_error
                body = r.structured_content["page_text"]
                if fault == "semantic": assert "150" in body and "120" not in body
                elif fault in {"request", "omission"}: assert "FY2025" not in body
                else: assert "120" in body
            if fault == "latency": assert elapsed >= 0.19
            calc = await c.call_tool("calculator", {"expression": "20+10"})
            assert calc.structured_content == {"result": 30.0} and not calc.is_error
            second = await c.call_tool("fetch_page", {"url": "fixture://acme/2025"})
            assert not second.is_error and "120" in second.structured_content["page_text"]
    run(check())
    rows = [json.loads(s) for s in (tmp_path / "log.jsonl").read_text().splitlines()]
    applied = [r for r in rows if r["event"] == "fault_applied"]
    assert len(applied) == (0 if fault == "disabled" else 1)
    assert all(r["tool"] == "fetch_page" for r in applied)


async def wire_proxy(tmp_path, cfg, linger=False):
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg))
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "faultlab.proxy", "--config", str(path),
        "--log", str(tmp_path / "log.jsonl"), "--", sys.executable,
        str(Path(__file__).with_name("wire_server.py")), str(tmp_path / "captured.in"), *(["linger"] if linger else []),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)


def request(i, tool="fetch_page"):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": tool, "arguments": {}}}


async def send(p, msg):
    p.stdin.write((json.dumps(msg) + "\n").encode())
    await p.stdin.drain()


async def receive(p):
    raw = await asyncio.wait_for(p.stdout.readline(), 5)
    assert raw, (await p.stderr.read()).decode()
    return json.loads(raw)


async def close(p):
    if p.returncode is None:
        p.stdin.close()
        try:
            await asyncio.wait_for(p.wait(), 5)
        except asyncio.TimeoutError:
            p.kill()
            await p.wait()
            raise


def test_byte_preserving_disabled_proxy_and_protocol_errors(tmp_path):
    async def check():
        p = await wire_proxy(tmp_path, config(enabled=False))
        try:
            raw = b'{ "jsonrpc" : "2.0", "method":"custom", "id":"10", "params":{"_meta":{"extra":"yes"}} }\n'
            note = b'{"jsonrpc":"2.0", "method":"notifications/cancelled", "params":{"requestId":99}}\n'
            p.stdin.write(note + raw)
            await p.stdin.drain()
            reply = await asyncio.wait_for(p.stdout.readline(), 5)
            assert reply == (tmp_path / "captured.out").read_bytes()
            assert (tmp_path / "captured.in").read_bytes() == note + raw
        finally: await close(p)
        assert p.returncode == 0
    run(check())


def test_delayed_reply_does_not_block_other_reply_or_mix_typed_ids(tmp_path):
    async def check():
        p = await wire_proxy(tmp_path, config("latency", parameters={"delay_ms": 400}))
        try:
            await send(p, request(1))
            await send(p, request("1", "calculator"))
            first = await receive(p)
            second = await receive(p)
            assert first["id"] == "1" and second["id"] == 1
        finally: await close(p)
        assert p.returncode == 0
    run(check())


def test_cancellation_discards_held_reply(tmp_path):
    async def check():
        p = await wire_proxy(tmp_path, config("latency", parameters={"delay_ms": 300}))
        try:
            await send(p, request(10))
            deadline = time.monotonic() + 5
            while not (tmp_path / "log.jsonl").exists() or "fault_scheduled" not in (tmp_path / "log.jsonl").read_text():
                assert time.monotonic() < deadline
                await asyncio.sleep(0.01)
            await send(p, {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 10}})
            await send(p, request(11, "calculator"))
            assert (await receive(p))["id"] == 11
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(p.stdout.readline(), 0.45)
        finally: await close(p)
        assert p.returncode == 0
    run(check())
    log = (tmp_path / "log.jsonl").read_text()
    assert "fault_cancelled" in log and "fault_applied" not in log


def test_upstream_failure_exits_nonzero_without_waiting_for_client_eof(tmp_path):
    async def check():
        p = await wire_proxy(tmp_path, config(enabled=False))
        try:
            await send(p, {"jsonrpc": "2.0", "id": 1, "method": "exit"})
            await asyncio.wait_for(p.wait(), 5)
            assert p.returncode != 0
            rows = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text().splitlines()]
            assert any(x["event"] == "upstream_exit" and x["returncode"] == 7 for x in rows)
        finally: await close(p)
    run(check())


def test_invalid_config_never_launches_upstream(tmp_path):
    async def check():
        p = await wire_proxy(tmp_path, config(probability=2))
        await asyncio.wait_for(p.wait(), 5)
        assert p.returncode != 0
        assert b"probability" in await p.stderr.read()
        assert not (tmp_path / "captured.in").exists()
        assert await p.stdout.read() == b""
    run(check())


def test_client_eof_cancels_hold_before_upstream_shutdown_finishes(tmp_path):
    async def check():
        p = await wire_proxy(tmp_path, config("latency", parameters={"delay_ms": 200}), linger=True)
        try:
            await send(p, request(10))
            deadline = time.monotonic() + 5
            while not (tmp_path / "log.jsonl").exists() or "fault_scheduled" not in (tmp_path / "log.jsonl").read_text():
                assert time.monotonic() < deadline
                await asyncio.sleep(0.01)
            await close(p)
            assert await p.stdout.read() == b""
        finally:
            await close(p)
    run(check())
    log = (tmp_path / "log.jsonl").read_text()
    assert "fault_cancelled" in log and "fault_applied" not in log


def test_real_sdk_timeout_cancels_fault_and_keeps_next_call_working(tmp_path):
    from mcp.shared.exceptions import MCPError
    async def check():
        cfg = config("latency", parameters={"delay_ms": 400}, occurrence=1)
        async with Client(sdk_params(tmp_path, cfg), mode="2026-07-28") as c:
            await c.list_tools()
            with pytest.raises(MCPError) as error:
                await c.call_tool("fetch_page", {"url": "fixture://acme/2025"}, read_timeout_seconds=0.05)
            assert "timed out" in str(error.value).lower()
            calc = await c.call_tool("calculator", {"expression": "6*7"})
            assert calc.structured_content == {"result": 42.0}
            await asyncio.sleep(0.45)
    run(check())
    rows = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert any(x["event"] == "fault_cancelled" for x in rows)
    assert not any(x["event"] == "fault_applied" for x in rows)
