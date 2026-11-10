# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`educelab-hpc` provides helpers for HPC environments (SLURM, Lmod, Apptainer, profiles, env paths, semver). It installs as `educelab.hpc` in the `educelab` namespace package and depends only on the standard library. Licensed under AGPLv3. Built from the `educelab-pymodule` template.

## Commands

Both pip and uv are supported. Don't introduce anything that requires uv.

```bash
# pip (25.1+ for --group)
pip install -e . --group dev
pytest                                        # all tests
pytest tests/test_semver.py::TestVersion      # single test
ruff check . && ruff format .

# uv equivalents
uv run pytest
uv run ruff check . && uv run ruff format .

uv build                       # or: python -m build
```

## Architecture and conventions

- **Namespace package:** `src/educelab/` must stay empty: no files, and no `__init__.py`. That is what lets several `educelab.*` distributions share the namespace.
- **Module code:** Everything lives in `src/educelab/hpc/`. The public API is re-exported from `__init__.py`.
- **Packaging:** All metadata lives in `pyproject.toml` (PEP 621, setuptools backend). There is no `setup.cfg` or `requirements.txt`.
- **Dependencies:** Keep runtime dependencies empty (stdlib only). Dev tools go in `[dependency-groups] dev` (PEP 735), which both pip and uv read.
- **Versioning:** The version is set statically in `pyproject.toml`. `__version__` reads it back through `importlib.metadata`. Pushing a `v*` tag publishes to PyPI via `.github/workflows/publish.yml`.
- **Tests:** Tests run under pytest with `--import-mode=importlib`, so `tests/` needs no `__init__.py`. Tests import from the installed package, so do an editable install first.
- **Typing:** The module ships a `py.typed` marker, included through `[tool.setuptools.package-data]`.
- **CI:** `.github/workflows/tests.yml` runs Ruff, then pytest on Linux, macOS, and Windows for every supported Python version. CI uses pip rather than uv on purpose, so it also confirms the project doesn't require uv. When you change the supported Python versions, update the matrix along with `requires-python` and the classifiers.
- **Python:** Requires 3.11 or newer.
