# EduceLab HPC

[![PyPI version](https://img.shields.io/pypi/v/educelab-hpc)](https://pypi.org/project/educelab-hpc/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/educelab-hpc)](https://pypi.org/project/educelab-hpc/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://github.com/educelab/educelab-hpc/actions/workflows/test.yml/badge.svg)](https://github.com/educelab/educelab-hpc/actions/workflows/test.yml)

`educelab-hpc` is a Python library providing helper functions for working in HPC environments. It covers SLURM job submission, Lmod environment module loading, Apptainer/Singularity container execution, inheritable configuration profiles, HPC path resolution, semantic versioning, and performance utilities — all with no runtime dependencies beyond the Python standard library (plus `tomli` on Python < 3.11).

## Installation

```bash
pip install educelab-hpc
```

## Modules

### SLURM (`educelab.hpc.slurm`)

Submit and manage SLURM batch jobs.

```python
from educelab.hpc import sbatch, SLURM_JOB_ID, SLURM_NODE_NAME
import os

# Submit a batch job (returns stdout, stderr)
stdout, stderr = sbatch(['my_job.sh', '--arg', 'value'])

# Access SLURM environment variables from within a running job
job_id = os.environ.get(SLURM_JOB_ID)
node = os.environ.get(SLURM_NODE_NAME)
```

`sbatch()` passes `--parsable` by default for machine-readable job ID output. Set `parsable=False` to disable.

To make local modules importable from within a SLURM script:

```python
from educelab.hpc.slurm import add_cwd_to_path
add_cwd_to_path()
```

### Lmod (`educelab.hpc.lmod`)

Load environment modules via the Lmod system.

```python
from educelab.hpc import module

module('load', 'ccs/singularity')
module('load', 'cuda/11.8')
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
containers = find_container('/path/to/sifs', 'myapp', version='>=1.0.0')
containers = find_container('/path/to/sifs', 'myapp', version=('>=1.0.0', '<2.0.0'))

# Run a container
apptainer_run(
    args=['python', 'script.py'],
    container=Path('/path/to/myapp-1.2.0.sif'),
    overlay=Path('/path/to/overlay.img'),  # optional persistent overlay
    enable_nv=True,                        # enable NVIDIA GPU passthrough
)
```

### Profiles (`educelab.hpc.profile`)

Keep Slurm accounts, partitions, GPU resources, modules, and storage roots in named TOML profiles instead of code, so the same scripts run anywhere by switching profiles. A profile can inherit from other profiles and add or override keys:

```toml
# ~/.config/educelab-hpc/profiles.toml  (or $XDG_CONFIG_HOME/educelab-hpc/)
active = "herc-lcc"

[profiles.lcc]
cpu_partition     = "CAL48M192_L"
gpu_partition     = "V4V32_SKY32M192_L"      # optional; omit for CPU-only clusters
gpu_gres          = "gpu:1"                  # optional
apptainer_modules = ["ccs/singularity"]      # optional

[profiles.herc-lcc]
inherits          = "lcc"
scratch_dir       = "$PSCRATCH/seales_uksr"  # ~ and env vars are expanded
project_dir       = "$PROJECT/seales_uksr"
cpu_account       = "col_seales_uksr"
gpu_account       = "gol_seales_uksr"        # optional; defaults to cpu_account
containers_dir    = "/shared/sif"            # optional; default <project_dir>/containers
```

`inherits` may also be a list. Parents apply in order (later ones win), and the profile's own keys win over all of them:

```toml
[profiles.herc]
globus_endpoint = "herc-archive"

[profiles.herc-ecc]
inherits = ["ecc", "herc"]
# ...ECC accounts and storage roots
```

Tables merge key by key through inheritance. Other values, lists included, replace what they inherit. The required keys (`scratch_dir`, `project_dir`, `cpu_account`, `cpu_partition`) are checked only on the profile you load, after inheritance, so they can come from any profile in its chain.

```python
from educelab.hpc import load_profile, export_profile, sbatch

profile = load_profile()           # or load_profile('herc-ecc')
export_profile(profile)            # queued jobs inherit this profile via $EL_PROFILE
sbatch(profile.sbatch_args(gpu=True) + ['job.sh'])

# Inside the job
profile = load_profile()
profile.load_apptainer_modules()
```

The profile is selected by an explicit name, then `$EL_PROFILE`, then the config's `active` key. Loading has no side effects. `export_profile()` is the one call that sets `$EL_PROFILE`, which `sbatch --export=ALL` (the default) forwards to the jobs you submit.

Profiles are frozen and fully resolved, and `profile.lineage` records the profiles merged to build one (e.g. `('lcc', 'herc-lcc')`). Keys the library doesn't recognize are kept in the read-only `profile.extra` mapping (use `profile.extra_path(key, default)` for path-valued ones). `resolve_table(name)` returns a profile's merged raw values for inspection. Applications can keep their own top-level tables in the same file and read them with `load_config()`.

An application can ship its own default profiles. The user config is merged on top key by key *before* inheritance is resolved, so a user's profile can inherit a shipped one, and a user tweak to a shipped profile reaches every profile that inherits it:

```python
profile = load_profile(defaults=Path(__file__).parent / 'profiles.toml')
```

### Environment Paths (`educelab.hpc.env`)

Access standard HPC directory environment variables as `pathlib.Path` objects.

```python
from educelab.hpc import PROJECT, PSCRATCH, SCRATCH

output_dir = SCRATCH / 'my_job' / 'results'
output_dir.mkdir(parents=True, exist_ok=True)
```

These resolve `$PROJECT`, `$PSCRATCH`, and `$SCRATCH` respectively and return `None` if the variable is unset.

### Local Execution (`educelab.hpc.local`)

Run shell commands as subprocesses with logging and automatic error handling.

```python
from educelab.hpc import run

run(['ffmpeg', '-i', 'input.mp4', 'output.mkv'])
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
v = Version('1.2.3-alpha+build')
v = Version(major=1, minor=2, patch=3)

# Compare versions
Version('1.1.0') > Version('1.0.0')  # True

# Check version requirements
req = VersionRequirement('>=1.0.0')
Version('1.5.0') == req   # True
Version('0.9.0') == req   # False

# Version ranges (auto-ordered)
req = VersionRequirement('>1.0.0', '<2.0.0')
Version('1.5.0') == req   # True
Version('2.0.1') == req   # False

# Extract version from an arbitrary string
v = get_version('myapp-container-v1.2.3-alpha+meta.sif')
# Version(1, 2, 3, 'alpha', 'meta')
```

## Development

```bash
git clone https://github.com/educelab/educelab-hpc.git
cd educelab-hpc
pip install -e ".[dev]"
pytest
```

## License

[GNU Affero General Public License v3](https://www.gnu.org/licenses/agpl-3.0)
