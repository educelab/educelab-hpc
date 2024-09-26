from .env import PROJECT, PSCRATCH, SCRATCH
from .lmod import module
from .local import run
from .singularity import run as singularity_run
from .slurm import sbatch, SLURM_JOB_ID, SLURM_NODE_NAME
