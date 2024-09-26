import logging
import os
import subprocess as sp
import sys
from typing import List

SLURM_JOB_ID = os.environ.get('SLURM_JOB_ID', None)
SLURM_NODE_NAME = os.environ.get('SLURMD_NODENAME', None)

def add_cwd_to_path():
    """Adds the current working directory to PATH. Call at the beginning of
    Python Slurm scripts in order to find local modules: https://stackoverflow.com/a/39574373"""
    sys.path.append(os.getcwd())


def sbatch(args: List[str], parsable=True):
    logger = logging.getLogger(__name__)
    cmd = ['sbatch']
    if parsable:
        cmd.append('--parsable')
    cmd.extend(args)
    logger.debug(f'running command: \'{" ".join(cmd)}\'')
    try:
        res = sp.run(cmd, check=True, capture_output=True)
    except sp.CalledProcessError as e:
        logger.debug('stdout:\n%s', e.stdout.decode())
        logger.debug('stderr:\n%s', e.stderr.decode())
        logger.exception('run failed', exc_info=e)
        sys.exit(e.returncode)
    except sp.SubprocessError as e:
        logger.exception('sbatch failed', exc_info=e)
        sys.exit(f'{e.args}')

    if parsable:
        return res.stdout.decode().strip(), res.stderr.decode().strip()
    else:
        return res.stdout.decode(), res.stderr.decode()
