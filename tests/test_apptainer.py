import subprocess as sp
import warnings

import pytest

import educelab.hpc
from educelab.hpc import apptainer


def test_find_container_unversioned_sorts_first(tmp_path):
    for name in ("myapp-2.0.0.sif", "myapp.sif", "myapp-latest.sif", "myapp-1.0.0.sif"):
        (tmp_path / name).touch()
    found = [p.name for p in apptainer.find_container(tmp_path, "myapp")]
    assert found == [
        "myapp-latest.sif",
        "myapp.sif",
        "myapp-1.0.0.sif",
        "myapp-2.0.0.sif",
    ]


def test_find_container_version_filter_skips_unversioned(tmp_path):
    for name in ("myapp.sif", "myapp-1.0.0.sif", "myapp-2.0.0.sif"):
        (tmp_path / name).touch()
    found = apptainer.find_container(tmp_path, "myapp", version=">=1.5.0")
    assert [p.name for p in found] == ["myapp-2.0.0.sif"]


def test_run_exits_with_container_return_code(monkeypatch):
    def fail(cmd, check):
        raise sp.CalledProcessError(137, cmd)

    monkeypatch.setattr(apptainer, "application", lambda: "apptainer")
    monkeypatch.setattr(apptainer.sp, "run", fail)
    with pytest.raises(SystemExit) as exc:
        apptainer.run(["--help"], container="app.sif")
    assert exc.value.code == 137


def test_singularity_run_warns_and_forwards(monkeypatch):
    calls = []
    monkeypatch.setattr(educelab.hpc, "apptainer_run", lambda *a, **k: calls.append(a))
    with pytest.warns(DeprecationWarning, match="apptainer_run"):
        educelab.hpc.singularity_run(["--help"], container="app.sif")
    assert calls == [(["--help"],)]


def test_singularity_run_leaves_warning_filters_alone(monkeypatch):
    monkeypatch.setattr(educelab.hpc, "apptainer_run", lambda *a, **k: None)
    # pytest.warns restores filters on exit, so check outside of it
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        before = list(warnings.filters)
        educelab.hpc.singularity_run(["--help"], container="app.sif")
        assert warnings.filters == before
