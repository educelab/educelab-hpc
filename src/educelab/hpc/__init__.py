from importlib.metadata import PackageNotFoundError, version

from .apptainer import run as apptainer_run
from .env import PROJECT, PSCRATCH, SCRATCH
from .lmod import module
from .local import run
from .perf import timedelta_str
from .profile import Profile, ProfileError, export_profile, load_profile
from .slurm import SLURM_JOB_ID, SLURM_NODE_NAME, sbatch

try:
    __version__ = version("educelab-hpc")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "PROJECT",
    "PSCRATCH",
    "SCRATCH",
    "SLURM_JOB_ID",
    "SLURM_NODE_NAME",
    "Profile",
    "ProfileError",
    "__version__",
    "apptainer_run",
    "export_profile",
    "load_profile",
    "module",
    "run",
    "sbatch",
    "singularity_run",
    "timedelta_str",
]


def singularity_run(*args, **kwargs):
    import warnings

    warnings.warn(
        "singularity_run is deprecated and will be removed "
        "in a future release. Use apptainer_run instead.",
        category=DeprecationWarning,
        stacklevel=2,
    )
    apptainer_run(*args, **kwargs)
