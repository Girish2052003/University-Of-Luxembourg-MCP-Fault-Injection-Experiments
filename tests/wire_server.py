"""Controlled wire-level test peer; SDK interoperability is tested separately."""
import json
import sys
import time
from pathlib import Path

capture = Path(sys.argv[1])
for line in sys.stdin.buffer:
    with capture.open("ab") as f:
        f.write(line)
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg.get("method") == "exit":
        sys.exit(7)
    if msg.get("method") == "tools/call":
        data = {"status": 200, "headers": {}, "page_text": "Revenue FY2025: EUR 120 million.\n"}
        result = {"resultType": "complete", "isError": False, "structuredContent": data,
                  "content": [{"type": "text", "text": json.dumps(data)}]}
        output = {"jsonrpc": "2.0", "id": msg["id"], "result": result, "custom": "preserve"}
    else:
        output = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "unknown"}}
    raw = (json.dumps(output, separators=(", ", " : "), ensure_ascii=False) + "\n").encode()
    with capture.with_suffix(".out").open("ab") as f:
        f.write(raw)
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()

if len(sys.argv) > 2 and sys.argv[2] == "linger":
    time.sleep(0.6)
