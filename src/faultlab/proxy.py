"""Transparent POSIX stdio proxy. Only selected calls pass through injectors."""
import argparse
import asyncio
from collections import OrderedDict
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
import time

from .evidence import Evidence
from .injectors import transform_request, transform_response
from .policy import Config, Decision, Policy, canonical

MAX_LINE_BYTES = 4 * 1024 * 1024
MAX_IN_FLIGHT = 1024


def key(value):
    return (type(value).__name__, value) if type(value) in (str, int) else None


def parsed(raw: bytes) -> dict:
    try:
        obj = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        return obj if isinstance(obj, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


@dataclass
class Pending:
    request_id: object
    tool: str | None
    decision: Decision | None
    cancelled: bool = False

    def fields(self):
        return {"request_id": self.request_id, "tool": self.tool,
                "ordinal": self.decision.ordinal if self.decision else None}


class Proxy:
    def __init__(self, config, evidence, upstream, output):
        self.config, self.log, self.upstream, self.output = config, evidence, upstream, output
        self.policy = Policy(config)
        self.pending = {}
        self.held = {}
        self.delay_tasks = set()
        self.cancelled = OrderedDict()
        self.closing = False
        self.output_lock = asyncio.Lock()
        self.fatal = asyncio.get_running_loop().create_future()

    async def write_client(self, raw):
        async with self.output_lock:
            self.output.write(raw)
            await self.output.drain()

    def change_event(self, state, phase, original, modified, detail):
        self.log.emit("fault_applied", **state.fields(), phase=phase, detail=detail,
                      before_sha256=hashlib.sha256(original).hexdigest(),
                      after_sha256=hashlib.sha256(modified).hexdigest())

    def cancel_hold(self, k, reason):
        entry = self.held.get(k)
        if entry:
            state, task = entry
            task.cancel()
            if not state.cancelled:
                state.cancelled = True
                self.log.emit("fault_cancelled", **state.fields(), reason=reason)

    def stop_holds(self, reason):
        self.closing = True
        # Cancel every task before logging: a failed log must not permit delivery.
        for task in self.delay_tasks:
            task.cancel()
        for k in list(self.held):
            self.cancel_hold(k, reason)

    async def from_client(self, raw):
        msg = parsed(raw)
        params = msg.get("params")
        params = params if isinstance(params, dict) else {}
        if msg.get("method") == "notifications/cancelled":
            k = key(params.get("requestId"))
            state = self.pending.pop(k, None)
            if state:
                self.cancel_hold(k, "client cancellation")
                state.cancelled = True
                self.cancelled[k] = state
                self.cancelled.move_to_end(k)
                if len(self.cancelled) > MAX_IN_FLIGHT:
                    self.cancelled.popitem(last=False)
        k = key(msg.get("id"))
        if k is not None and isinstance(msg.get("method"), str):
            if k in self.pending:
                raise ValueError("duplicate in-flight request ID")
            if len(self.pending) >= MAX_IN_FLIGHT:
                raise ValueError("in-flight request limit exceeded")
            self.cancelled.pop(k, None)
            tool = params.get("name") if msg["method"] == "tools/call" else None
            decision = self.policy.decide(tool)
            state = Pending(msg["id"], tool, decision)
            self.pending[k] = state
            if decision:
                self.log.emit("decision", **state.fields(), selected=decision.selected, draw=decision.draw)
            if decision and decision.selected and self.config.fault == "request":
                changed, detail = transform_request(msg, self.config)
                if changed is None:
                    self.log.emit("fault_skipped", **state.fields(), phase="request", **detail)
                else:
                    new = canonical(changed) + b"\n"
                    self.change_event(state, "request", raw, new, detail)
                    raw = new
        self.upstream.stdin.write(raw)
        await self.upstream.stdin.drain()

    async def deliver_delayed(self, k, state, raw, detail):
        start = time.monotonic()
        try:
            await asyncio.sleep(self.config.parameters["delay_ms"] / 1000)
            detail = {**detail, "observed_delay_ms": (time.monotonic() - start) * 1000}
            self.change_event(state, "response", raw, raw, detail)
            await self.write_client(raw)
            self.log.emit("fault_delivered", **state.fields(), phase="response")
        finally:
            # An old cancelled task must not remove a newer request reusing its ID.
            if self.pending.get(k) is state:
                self.pending.pop(k)

    def delayed_done(self, k, task):
        self.delay_tasks.discard(task)
        if k in self.held and self.held[k][1] is task:
            self.held.pop(k)
        if not task.cancelled():
            error = task.exception()
            if error is not None and not self.fatal.done():
                self.fatal.set_result(error)

    async def from_server(self, raw):
        msg = parsed(raw)
        k = key(msg.get("id"))
        is_response = "method" not in msg and bool({"result", "error"} & msg.keys())
        if is_response and k in self.cancelled:
            state = self.cancelled.pop(k)
            self.log.emit("response_discarded", **state.fields(), reason="cancelled request")
            return
        state = self.pending.get(k)
        # Never mistake notifications or server requests for client responses.
        if state is None or not is_response:
            await self.write_client(raw)
            return
        if state.cancelled:
            self.pending.pop(k, None)
            self.log.emit("response_discarded", **state.fields(), reason="cancelled request")
            return
        decision = state.decision
        if decision and decision.selected and self.config.fault != "request":
            changed, detail = transform_response(msg, self.config)
            if changed is None:
                self.log.emit("fault_skipped", **state.fields(), phase="response", **detail)
            elif self.config.fault == "latency":
                if self.closing:
                    self.pending.pop(k, None)
                    self.log.emit("fault_cancelled", **state.fields(), reason="client EOF before hold")
                    return
                self.log.emit("fault_scheduled", **state.fields(), **detail)
                task = asyncio.create_task(self.deliver_delayed(k, state, raw, detail))
                self.held[k] = (state, task)
                self.delay_tasks.add(task)
                task.add_done_callback(lambda t, selected=k: self.delayed_done(selected, t))
                return
            else:
                new = canonical(changed) + b"\n"
                self.change_event(state, "response", raw, new, detail)
                raw = new
                await self.write_client(raw)
                self.log.emit("fault_delivered", **state.fields(), phase="response")
                self.pending.pop(k, None)
                return
        await self.write_client(raw)
        self.pending.pop(k, None)


async def serve(config, log, command):
    if sys.platform == "win32":
        raise RuntimeError("Run this stdio proxy in Linux, macOS or Windows Subsystem for Linux (WSL)")
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_LINE_BYTES)
    read_transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin.buffer)
    write_transport, write_protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout.buffer)
    output = asyncio.StreamWriter(write_transport, write_protocol, None, loop)
    upstream = None
    tasks = []
    proxy = None
    client_eof = False
    try:
        upstream = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=None, limit=MAX_LINE_BYTES)
        log.emit("upstream_started", pid=upstream.pid, protocol_tested="2026-07-28")
        proxy = Proxy(config, log, upstream, output)

        async def client_pump():
            nonlocal client_eof
            while raw := await reader.readline():
                await proxy.from_client(raw)
            client_eof = True
            proxy.stop_holds("client EOF")
            upstream.stdin.close()

        async def server_pump():
            while raw := await upstream.stdout.readline():
                await proxy.from_server(raw)

        c = asyncio.create_task(client_pump())
        s = asyncio.create_task(server_pump())
        tasks = [c, s]
        done, _ = await asyncio.wait([c, s, proxy.fatal], return_when=asyncio.FIRST_COMPLETED)
        if proxy.fatal in done:
            raise proxy.fatal.result()
        for task in done:
            task.result()
        if client_eof:
            await asyncio.wait_for(s, 2)
        returncode = await asyncio.wait_for(upstream.wait(), 2)
        log.emit("upstream_exit", returncode=returncode)
        if returncode != 0 or not client_eof:
            raise RuntimeError(f"upstream ended unexpectedly (exit={returncode})")
    finally:
        cleanup_error = None
        for task in tasks:
            task.cancel()
        if proxy:
            tasks.extend(list(proxy.delay_tasks))
            try:
                proxy.stop_holds("proxy shutdown")
            except (OSError, ValueError) as exc:
                cleanup_error = exc
        await asyncio.gather(*tasks, return_exceptions=True)
        if upstream and upstream.returncode is None:
            if upstream.stdin:
                upstream.stdin.close()
            try:
                await asyncio.wait_for(upstream.wait(), 1)
            except asyncio.TimeoutError:
                upstream.terminate()
                try:
                    await asyncio.wait_for(upstream.wait(), 1)
                except asyncio.TimeoutError:
                    upstream.kill()
                    await upstream.wait()
        read_transport.close()
        write_transport.close()
        if cleanup_error:
            raise cleanup_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path, help="new JSONL path; existing logs are never overwritten")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    try:
        if not command:
            raise ValueError("an upstream command is required after --")
        config = Config.from_dict(json.loads(args.config.read_text(encoding="utf-8")))
        with Evidence(args.log, config) as log:
            log.emit("run_started", config=asdict(config), python=sys.version.split()[0])
            asyncio.run(serve(config, log, command))
            log.emit("run_finished")
    except (OSError, ValueError, RuntimeError, asyncio.TimeoutError) as exc:
        print(f"mcp-faultlab: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
