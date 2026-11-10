"""Real SDK server with fixed synthetic pages and bounded arithmetic; no network."""
import ast
import math
import operator
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

server = MCPServer("MCP-FaultLab synthetic tools", log_level="WARNING")


class Page(BaseModel):
    status: int
    headers: dict[str, str]
    page_text: str


PAGES = {
    "fixture://acme/2025": "ACME SYNTHETIC annual comparison\nRevenue FY2024: EUR 100 million.\nRevenue FY2025: EUR 120 million.\n",
    "fixture://acme/2024": "ACME SYNTHETIC annual comparison\nRevenue FY2023: EUR 80 million.\nRevenue FY2024: EUR 100 million.\n",
}


@server.tool()
def web_search(query: str) -> list[dict[str, str]]:
    """Search the fixed synthetic catalog; this never accesses the web."""
    return [{"title": "ACME synthetic annual comparison", "url": "fixture://acme/2025"}] if "acme" in query.lower() else []


@server.tool()
def fetch_page(url: str) -> Page:
    """Return a fixed synthetic page, HTTP-like status, and headers."""
    if url not in PAGES:
        raise ToolError("Unknown local fixture URL")
    return Page(status=200, headers={"content-type": "text/plain", "x-data-origin": "synthetic"}, page_text=PAGES[url])


def arithmetic(expression: str) -> float:
    if len(expression) > 256:
        raise ValueError("expression too long")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError("expression too complex")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            value = operations[type(node.op)](visit(node.left), visit(node.right))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        else:
            raise ValueError("only numbers, parentheses and + - * / are allowed")
        if not math.isfinite(value) or abs(value) > 1e12:
            raise ValueError("numeric result outside supported bounds")
        return value
    return visit(tree.body)


@server.tool()
def calculator(expression: str) -> float:
    """Evaluate bounded arithmetic without eval, names, calls, or powers."""
    try:
        return arithmetic(expression)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise ToolError(str(exc)) from exc


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
