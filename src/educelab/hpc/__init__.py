from .apptainer import run as apptainer_run
from .env import PROJECT, PSCRATCH, SCRATCH
from .lmod import module
from .local import run
from .perf import timedelta_str
from .slurm import sbatch, SLURM_JOB_ID, SLURM_NODE_NAME


def singularity_run(*args, **kwargs):
    import warnings
    warnings.simplefilter('always', DeprecationWarning)
    warnings.warn(f'singularity_run is deprecated and will be removed '
                  f'in a future release. Use apptainer_run instead.',
                  category=DeprecationWarning,
                  stacklevel=2)
    warnings.simplefilter('default', DeprecationWarning)
    apptainer_run(*args, **kwargs)