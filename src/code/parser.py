
import ast


def parse_code(source: str) -> ast.Module:
    return ast.parse(source)
