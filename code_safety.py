"""Static safety validation for LLM-generated Manim code (defense-in-depth).

The render step EXECUTES generated Python: ``manim scene.py GenScene`` imports the
module and runs ``construct()``. Until now the only pre-render check was *syntax*
(``common.looks_truncated`` / ``py_compile``) — nothing stopped a prompt-injected or
hallucinated ``import os; os.system(...)`` from running, and the primary render path is
a GitHub Actions worker that holds repo secrets. This module is the missing gate.

It is an AST allowlist, not a real sandbox: it permits only a curated set of pure,
no-I/O imports and rejects the obvious code-execution / file / network / introspection
escape vectors. It is deliberately **dependency-free (stdlib ``ast`` only)** so the
exact same check can run on the minimal cloud worker (see ``deploy/ci_render.py``).

Usage:
    ok, issues = validate_code_safety(code)
    if not ok:
        ...  # refuse to render; fail closed
"""
from __future__ import annotations

import ast

# Top-level module roots a generated scene may import. All are pure / no-I/O /
# no-subprocess / no-network. `from manim import *` + `import numpy as np` +
# `import math` is what every template/recipe emits; the rest are safe extras a
# scene might reach for (kept tight to minimise the attack surface).
_ALLOWED_IMPORT_ROOTS: frozenset[str] = frozenset({
    "manim", "numpy", "math", "cmath", "random", "statistics",
    "itertools", "functools", "operator", "fractions", "decimal",
    "typing", "dataclasses", "collections", "enum", "string", "json",
    "__future__",
})

# Builtins that have no legitimate place in a Manim scene and are the usual
# code-execution / file / introspection primitives. Flagged wherever they appear
# as a bare name (a method call like ``obj.open()`` is an Attribute, not a Name,
# so it is NOT caught here — only the dangerous builtin ``open(...)`` is).
_BANNED_NAMES: frozenset[str] = frozenset({
    "exec", "eval", "compile", "__import__", "open", "input",
    "breakpoint", "globals", "locals", "vars",
})

# Attribute names that signal a sandbox-escape chain
# (e.g. ``().__class__.__bases__[0].__subclasses__()``) or interpreter internals.
_BANNED_DUNDERS: frozenset[str] = frozenset({
    "__globals__", "__builtins__", "__subclasses__", "__bases__",
    "__mro__", "__code__", "__import__", "__loader__", "__spec__",
})

_MAX_ISSUES = 20  # cap the report so a pathological file can't flood logs


def _import_root(name: str | None) -> str:
    """Top-level package of a dotted import name ('a.b.c' -> 'a')."""
    return (name or "").split(".")[0]


def validate_code_safety(code: str) -> tuple[bool, list[str]]:
    """Return ``(is_safe, issues)`` for a generated Manim scene.

    Safety only — NOT syntax: code that fails to parse returns ``(True, [])`` so the
    existing truncation/repair path still owns syntax errors. A non-empty ``issues``
    list means the code must NOT be rendered (fail closed).
    """
    if not code or not code.strip():
        return True, []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Not our concern — let the syntax/truncation handling deal with it.
        return True, []

    issues: list[str] = []

    def add(msg: str) -> None:
        if msg not in issues and len(issues) < _MAX_ISSUES:
            issues.append(msg)

    for node in ast.walk(tree):
        # Imports — allowlist only.
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _import_root(alias.name)
                if root not in _ALLOWED_IMPORT_ROOTS:
                    add(f"disallowed import: '{alias.name}' (only {sorted(_ALLOWED_IMPORT_ROOTS)} are permitted)")
        elif isinstance(node, ast.ImportFrom):
            # Relative imports (level>0) have no allowlisted root → reject.
            root = _import_root(node.module) if node.level == 0 else ""
            if root not in _ALLOWED_IMPORT_ROOTS:
                target = ("." * node.level) + (node.module or "")
                add(f"disallowed import: 'from {target} import ...'")
        # Dangerous builtins referenced by bare name.
        elif isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            add(f"disallowed builtin: '{node.id}'")
        # Sandbox-escape / interpreter-internal attribute access.
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_DUNDERS:
            add(f"disallowed attribute access: '.{node.attr}'")

    return (not issues), issues


def safety_report(code: str) -> str:
    """One-line human-readable summary (empty string when safe)."""
    ok, issues = validate_code_safety(code)
    if ok:
        return ""
    return "Unsafe code rejected — " + "; ".join(issues)


if __name__ == "__main__":  # tiny smoke check
    good = "from manim import *\nimport numpy as np\nclass GenScene(Scene):\n    def construct(self):\n        self.add(Dot())\n"
    bad = "import os\nos.system('id')\n"
    print("good:", validate_code_safety(good))
    print("bad :", validate_code_safety(bad))
