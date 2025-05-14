import logging
import shutil
import subprocess as sp
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Union

from educelab.hpc.semver import VersionRequirement, get_version


def application() -> Optional[str]:
    for name in ('apptainer', 'singularity'):
        path = shutil.which(name)
        if path is not None:
            return name
    return None


def find_container(root,
                   name,
                   version: Union[str,
                   Tuple[str, str]] = None) -> List[Path]:
    # TODO: Extensions other than .sif
    containers = list(Path(root).rglob(f'{name}*.sif'))

    # Build the version filter
    version_filter = lambda x: True
    if version is not None:
        # split min,max requirements
        if isinstance(version, str):
            version = (version,)
        req = VersionRequirement(*version)
        version_filter = lambda x: x == req

    # filter by version
    filtered = []
    for c in containers:
        c = Path(c)
        ver = get_version(c.stem)
        if version_filter(ver):
            filtered.append((ver, c))
    filtered = sorted(filtered, key=lambda x: x[0])

    # return as list of paths
    return [f[1] for f in filtered]


def run(args: List[str], container, overlay=None, enable_nv=False):
    """
    Run an apptainer/singularity container
    :param args: Arguments to pass to the container
    :param container: Path to a container
    :param overlay: (optional) Path to a persistent overlay file
    :param enable_nv: (optional) Enable Nvidia passthrough support
    :return:
    """
    logger = logging.getLogger(__name__)
    app = application()
    if app is None:
        raise RuntimeError('apptainer/singularity not detected!')
    cmd = [app, 'run']
    if enable_nv:
        cmd.extend(['--nv'])
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
