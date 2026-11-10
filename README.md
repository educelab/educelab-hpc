# EduceLab HPC

[![PyPI version](https://img.shields.io/pypi/v/educelab-hpc)](https://pypi.org/project/educelab-hpc/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/educelab-hpc)](https://pypi.org/project/educelab-hpc/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://github.com/educelab/educelab-hpc/actions/workflows/tests.yml/badge.svg)](https://github.com/educelab/educelab-hpc/actions/workflows/tests.yml)

`educelab-hpc` is a Python library providing helper functions for working in HPC environments. It covers SLURM job submission, Lmod environment module loading, Apptainer/Singularity container execution, inheritable configuration profiles, HPC path resolution, semantic versioning, and performance utilities. It requires Python 3.11 or newer and depends only on the standard library.

## Installation

```bash
pip install educelab-hpc
```

## Modules

### SLURM (`educelab.hpc.slurm`)

Submit and manage SLURM batch jobs.

```python
from educelab.hpc import sbatch, SLURM_JOB_ID, SLURM_NODE_NAME

# Submit a batch job; with --parsable (the default), stdout is the job ID
job_id, stderr = sbatch(["my_job.sh", "--arg", "value"])

# Inside a running job: the job ID and node name, or None outside a job
print(SLURM_JOB_ID, SLURM_NODE_NAME)
```

`sbatch()` passes `--parsable` by default for machine-readable job ID output. Set `parsable=False` to disable. If `sbatch` fails, the error is logged and the process exits with its return code. `SLURM_JOB_ID` and `SLURM_NODE_NAME` are read from the environment when `educelab.hpc` is imported.

To make local modules importable from within a SLURM script:

```python
from educelab.hpc.slurm import add_cwd_to_path

add_cwd_to_path()
```

### Lmod (`educelab.hpc.lmod`)

Load environment modules via the Lmod system.

```python
from educelab.hpc import module

module("load", "ccs/singularity")
module("load", "cuda/11.8")
```

The module executable is located via `$LMOD_CMD` when set, with a fallback to the LCC OpenHPC default path.

### Apptainer / Singularity (`educelab.hpc.apptainer`)

Detect and run Apptainer or Singularity containers.

```python
from educelab.hpc import apptainer_run
from educelab.hpc.apptainer import application, find_container
from pathlib import Path

# Detect which container runtime is available
app = application()  # 'apptainer', 'singularity', or None

# Find .sif files matching a name and optional version constraint
containers = find_container("/path/to/sifs", "myapp", version=">=1.0.0")
containers = find_container("/path/to/sifs", "myapp", version=(">=1.0.0", "<2.0.0"))

# Run a container
apptainer_run(
    args=["python", "script.py"],
    container=Path("/path/to/myapp-1.2.0.sif"),
    overlay=Path("/path/to/overlay.img"),  # optional persistent overlay
    enable_nv=True,  # enable NVIDIA GPU passthrough
)
```

`find_container()` searches `root` recursively and returns matches sorted by the version in their filenames, oldest first, so the newest is `[-1]`. `apptainer_run()` raises `RuntimeError` if neither runtime is installed, and logs the error and exits the process if the container fails.

### Profiles (`educelab.hpc.profile`)

A profile is a named set of Slurm, module, and storage settings kept in TOML instead of code, so the same scripts run on any cluster or allocation by switching profiles. Profiles can inherit from other profiles, so shared settings are written once.

```toml
# ~/.config/educelab-hpc/profiles.toml  (or $XDG_CONFIG_HOME/educelab-hpc/profiles.toml)
active = "myproject-lcc"

[profiles.lcc]
cpu_partition     = "CAL48M192_L"
gpu_partition     = "V4V32_SKY32M192_L"
gpu_gres          = "gpu:1"
apptainer_modules = ["ccs/singularity"]

[profiles.myproject-lcc]
inherits    = "lcc"
scratch_dir = "$PSCRATCH/myproject"
project_dir = "$PROJECT/myproject"
cpu_account = "col_myproject"
gpu_account = "gol_myproject"
```

#### Submitting and running jobs

```python
# submit.py
from educelab.hpc import export_profile, load_profile, sbatch

profile = load_profile()  # the selected profile (see below)
export_profile(profile)  # jobs submitted from here select it too
sbatch(profile.sbatch_args(gpu=True) + ["job.py"])
```

```python
# job.py
from educelab.hpc import apptainer_run, load_profile

profile = load_profile()  # reads $EL_PROFILE, set by the submitter
profile.load_apptainer_modules()
apptainer_run(["--help"], container=profile.containers_dir / "myapp-1.0.0.sif")
```

`export_profile()` sets `$EL_PROFILE`, which Slurm forwards to the job (`--export=ALL` is the default). Only the name is forwarded, so the job loads the profile again from the config as it is when the job starts.

#### Selecting a profile

`load_profile()` uses the first of:

1. the name passed to it, e.g. `load_profile('myproject-ecc')`
2. `$EL_PROFILE`
3. the config's top-level `active` key

Loading never changes the environment; only `export_profile()` does.

#### Keys

| Key | Required | Default | Meaning |
| --- | --- | --- | --- |
| `scratch_dir` | yes | | Scratch storage root |
| `project_dir` | yes | | Persistent project storage root |
| `cpu_account` | yes | | Slurm account for CPU jobs (`-A`) |
| `cpu_partition` | yes | | Slurm partition for CPU jobs (`-p`) |
| `gpu_account` | no | `cpu_account` | Slurm account for GPU jobs |
| `gpu_partition` | no | none | Slurm partition for GPU jobs; without it the profile is CPU-only |
| `gpu_gres` | no | none | GPU resource request, e.g. `gpu:1` or `h100:1` |
| `apptainer_modules` | no | none | Lmod modules that provide `apptainer` |
| `containers_dir` | no | `<project_dir>/containers` | Container image directory |
| `inherits` | no | none | Profile name, or list of names, to inherit from |

Paths expand `~` and environment variables. A path that uses an unset variable is an error, rather than quietly becoming a relative path. Required keys are checked on the profile you load, after inheritance, so they can come from any profile it inherits. Any other key is kept for your application (see [Application settings](#application-defaults-and-settings)).

#### Inheritance

- Parents apply in the order listed: later parents override earlier ones, and the profile's own keys override all of them.
- Tables merge key by key. Any other value, lists included, replaces the inherited one.
- Set a key to `""` to unset an inherited value, e.g. `gpu_partition = ""` for a CPU-only profile.
- A profile reached along more than one path is merged once, at its first position, so it can't undo a profile that already overrode it.
- `profile.lineage` lists the profiles merged, in order, e.g. `('lcc', 'myproject-lcc')`.

Inheriting from a list lets a project share settings across clusters:

```toml
[profiles.ecc]
cpu_partition     = "H4V80_ICE64M512_L"
gpu_partition     = "H4V80_ICE64M512_L"
gpu_gres          = "h100:1"
apptainer_modules = ["ecc/spack/0.23.1", "apptainer/1.3.6-m6hnups"]

[profiles.myproject]              # shared by every myproject-* profile
globus_endpoint = "myproject-archive"

[profiles.myproject-ecc]
inherits    = ["ecc", "myproject"]
scratch_dir = "$PSCRATCH/myproject"
project_dir = "$PROJECT/myproject"
cpu_account = "ecc_myproject"
```

#### Application defaults and settings

An application can ship default profiles, as a TOML file or a dict. The user config is merged over them key by key before inheritance is resolved, so a user's profile can inherit a shipped one, and a user's change to a shipped profile reaches every profile that inherits it. Pass the same `defaults` in the submitter and the job:

```python
# myapp/config.py
from pathlib import Path
from educelab.hpc import load_profile

DEFAULTS = Path(__file__).parent / "profiles.toml"


def profile(name=None):
    return load_profile(name, defaults=DEFAULTS)
```

Locate the file from a module the job imports, not from the script you submit: Slurm runs a copy of the submitted script from its spool directory, so a path relative to that script's `__file__` doesn't exist.

Keys the library doesn't recognize, like `globus_endpoint` above, are kept in the read-only `profile.extra` mapping, and `profile.extra_path(key, default)` expands a path-valued one. Applications can also keep their own top-level tables in the same file and read the merged config with `educelab.hpc.profile.load_config(defaults)`. To check what a profile inherits, `educelab.hpc.profile.resolve_table(name)` returns its merged, unexpanded values.

#### Errors

Config problems raise `ProfileError` (importable from `educelab.hpc`) with a message naming the profile or file. That covers no profile being selected, an unknown profile or parent, an inheritance cycle, missing required keys, wrongly typed values, invalid TOML, a missing `defaults` file, and a path that uses an unset environment variable.

### Environment Paths (`educelab.hpc.env`)

Access standard HPC directory environment variables as `pathlib.Path` objects.

```python
from educelab.hpc import PROJECT, PSCRATCH, SCRATCH

if SCRATCH is None:
    raise SystemExit("$SCRATCH is not set")
output_dir = SCRATCH / "my_job" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
```

These hold `$PROJECT`, `$PSCRATCH`, and `$SCRATCH` as paths, or `None` if the variable is unset or empty. They're read when `educelab.hpc` is first imported.

### Local Execution (`educelab.hpc.local`)

Run shell commands as subprocesses with logging and automatic error handling.

```python
from educelab.hpc import run

run(["ffmpeg", "-i", "input.mp4", "output.mkv"])
```

Logs the command at DEBUG level and exits the process on failure.

### Performance Utilities (`educelab.hpc.perf`)

Format timing information for human-readable output.

```python
from datetime import timedelta
from educelab.hpc import timedelta_str

delta = timedelta(days=1, hours=2, minutes=30, seconds=45)
print(timedelta_str(delta))  # "1d2h30m45s"
```

Components are omitted when zero (e.g. `"5m10s"` instead of `"0d0h5m10s"`).

### Semantic Versioning (`educelab.hpc.semver`)

Parse and compare semantic versions and version constraints. Useful for filtering container images by version.

```python
from educelab.hpc.semver import Version, VersionRequirement, get_version

# Parse versions
v = Version("1.2.3-alpha+build")
v = Version(major=1, minor=2, patch=3)

# Compare versions
Version("1.1.0") > Version("1.0.0")  # True

# Check version requirements
req = VersionRequirement(">=1.0.0")
Version("1.5.0") == req  # True
Version("0.9.0") == req  # False

# Version ranges (auto-ordered)
req = VersionRequirement(">1.0.0", "<2.0.0")
Version("1.5.0") == req  # True
Version("2.0.1") == req  # False

# Extract version from an arbitrary string
v = get_version("myapp-container-v1.2.3-alpha+meta.sif")
# Version(1, 2, 3, 'alpha', 'meta')
```

## Development

Either pip or [uv](https://docs.astral.sh/uv/) can be used.

With pip (25.1+):
```bash
git clone https://github.com/educelab/educelab-hpc.git
cd educelab-hpc
python -m venv .venv
source .venv/bin/activate
pip install -e . --group dev
pytest
ruff check . && ruff format .
```

With uv:
```bash
uv run pytest
uv run ruff check . && uv run ruff format .
```

## License

[GNU Affero General Public License v3](https://www.gnu.org/licenses/agpl-3.0)
