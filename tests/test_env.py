import importlib
from pathlib import Path

from educelab.hpc import env


def reload_with(monkeypatch, **values):
    for name in ("PROJECT", "PSCRATCH", "SCRATCH"):
        if name in values:
            monkeypatch.setenv(name, values[name])
        else:
            monkeypatch.delenv(name, raising=False)
    return importlib.reload(env)


def test_set_variables_are_paths(monkeypatch):
    mod = reload_with(monkeypatch, PROJECT="/project/x", SCRATCH="/scratch/x")
    assert mod.PROJECT == Path("/project/x")
    assert mod.SCRATCH == Path("/scratch/x")


def test_unset_or_empty_variables_are_none(monkeypatch):
    mod = reload_with(monkeypatch, SCRATCH="")
    assert mod.PROJECT is None
    assert mod.PSCRATCH is None
    assert mod.SCRATCH is None


def teardown_module():
    importlib.reload(env)
