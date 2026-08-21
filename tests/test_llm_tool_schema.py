from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARG_PATTERN = re.compile(r"^\s*(\w+)\((string|number|object|boolean|array(?:\[\w+\])?)\):\s*.+$")


class LlmToolSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))

    def test_every_llm_tool_argument_is_documented(self):
        tools = []
        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            if not any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "llm_tool"
                for decorator in node.decorator_list
            ):
                continue
            tools.append(node)
            doc = ast.get_docstring(node) or ""
            documented = {
                match.group(1)
                for line in doc.splitlines()
                if (match := ARG_PATTERN.match(line))
            }
            parameters = [arg.arg for arg in node.args.args if arg.arg not in {"self", "event"}]
            self.assertEqual(set(parameters), documented, node.name)
        self.assertGreaterEqual(len(tools), 9)

    def test_llm_tools_do_not_expose_delete_or_unlock(self):
        tool_names = set()
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "llm_tool"
                ):
                    continue
                for keyword in decorator.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        tool_names.add(str(keyword.value.value))
        self.assertFalse(any("delete" in name or "unlock" in name for name in tool_names))


if __name__ == "__main__":
    unittest.main()
