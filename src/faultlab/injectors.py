"""Narrow, schema-preserving transforms for the documented demo shapes."""
import copy
import json
from mcp.types import CallToolResult
from pydantic import ValidationError
from .policy import Config


def _skip(reason: str):
    return None, {"reason": reason}


def transform_request(message: dict, config: Config) -> tuple[dict | None, dict]:
    params = message.get("params")
    args = params.get("arguments") if isinstance(params, dict) else None
    p = config.parameters
    if not isinstance(args, dict) or args.get(p["argument"]) != p["old"]:
        return _skip("request argument does not match configured original")
    changed = copy.deepcopy(message)
    changed["params"]["arguments"][p["argument"]] = p["new"]
    return changed, {"field": "params.arguments." + p["argument"], "old": p["old"], "new": p["new"]}


def transform_response(message: dict, config: Config) -> tuple[dict | None, dict]:
    result = message.get("result")
    if (not isinstance(result, dict) or "error" in message or
            result.get("isError", False) is not False or result.get("resultType") != "complete"):
        return _skip("not a successful complete modern tool result")
    try:
        # Validate a copy for eligibility, but never reserialize untouched traffic.
        CallToolResult.model_validate(result, strict=True)
    except ValidationError:
        return _skip("malformed complete tool result")
    changed = copy.deepcopy(message)
    if config.fault == "latency":
        return changed, {"delay_ms": config.parameters["delay_ms"]}
    if config.fault == "error":
        r = changed["result"]
        r.pop("structuredContent", None)
        r["isError"] = True
        r["content"] = [{"type": "text", "text": config.parameters["message"]}]
        return changed, {"message": config.parameters["message"], "upstream_executed": True}
    data, content = result.get("structuredContent"), result.get("content")
    if not isinstance(data, dict) or not isinstance(data.get("page_text"), str):
        return _skip("expected structuredContent.page_text string")
    if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict)
            or content[0].get("type") != "text" or not isinstance(content[0].get("text"), str)):
        return _skip("expected one JSON text copy of structuredContent")
    try:
        if json.loads(content[0]["text"]) != data:
            return _skip("text and structured representations disagree")
    except (ValueError, TypeError):
        return _skip("text copy is not JSON")
    old = config.parameters["old"]
    new = "" if config.fault == "omission" else config.parameters["new"]
    if data["page_text"].count(old) != 1:
        return _skip("expected exactly one matching factual span")
    d = changed["result"]["structuredContent"]
    d["page_text"] = d["page_text"].replace(old, new, 1)
    changed["result"]["content"][0]["text"] = json.dumps(d, ensure_ascii=False)
    return changed, {"field": "result.structuredContent.page_text (+text copy)", "old": old, "new": new}
