import tomllib
from pathlib import Path


def test_lingneng_package_is_in_setuptools_find_include():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "lingneng" in include
    assert "lingneng.*" in include
