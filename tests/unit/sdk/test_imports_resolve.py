"""Every in-package `from .x import name` resolves, including imports deferred
inside functions (CLI commands import lazily, so a removed name only fails when
that command runs)."""

import ast
import importlib
from pathlib import Path

import pytest

import monarch

PKG_ROOT = Path(monarch.__file__).parent


def _relative_imports():
    for path in sorted(PKG_ROOT.rglob("*.py")):
        module = "monarch." + ".".join(path.relative_to(PKG_ROOT).with_suffix("").parts)
        module = module.removesuffix(".__init__")
        package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                target = f"{base}.{node.module}" if node.module else base
                for alias in node.names:
                    yield pytest.param(target, alias.name, id=f"{path.name}:{node.lineno}:{alias.name}")


@pytest.mark.parametrize("target,name", list(_relative_imports()))
def test_relative_import_resolves(target, name):
    mod = importlib.import_module(target)
    if not hasattr(mod, name):
        importlib.import_module(f"{target}.{name}")  # submodule import
