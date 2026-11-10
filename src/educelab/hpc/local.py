import logging
import subprocess as sp
import sys


def run(cmd: list[str]):
    logger = logging.getLogger(__name__)
    logger.debug(f"running command: '{' '.join(cmd)}'")
    try:
        return sp.run(cmd, check=True)
    except sp.SubprocessError as e:
        logger.exception("run failed", exc_info=e)
        sys.exit(f"{e.args}")
