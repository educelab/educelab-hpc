import logging
import subprocess as sp
import sys
from typing import List


def run(args: List[str], container, overlay=None):
    logger = logging.getLogger(__name__)
    cmd = ['singularity', 'run']
    if overlay is not None:
        cmd.extend(['--overlay', str(overlay)])
    cmd.append(str(container))
    cmd.extend(args)
    logger.debug(f'running command: \'{" ".join(cmd)}\'')
    try:
        sp.run(cmd, check=True)
    except sp.SubprocessError as e:
        logger.exception('singularity run failed', exc_info=e)
        sys.exit(f'{e.args}')
