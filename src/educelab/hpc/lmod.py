import os
import subprocess as sp
import sys

# LCC's OpenHPC layout. Used as a fallback only when $LMOD_CMD is unset.
LMOD_DEFAULT = '/opt/ohpc/admin/lmod/lmod/libexec/lmod'


def module(command, *arguments):
    """For loading lmod modules, e.g. 'module load ccs/singularity'"""
    # Lmod exports $LMOD_CMD in an initialized environment; it points at the
    # lmod executable and is portable across clusters (LCC, ECC, etc.). Fall
    # back to the LCC path only when the variable is unset.
    lmod_cmd = os.environ.get('LMOD_CMD', LMOD_DEFAULT)
    if not os.path.exists(lmod_cmd):
        raise FileNotFoundError(
            f"Could not locate the lmod executable at '{lmod_cmd}'. Set "
            "$LMOD_CMD or ensure the Lmod module system is initialized.")
    proc = sp.Popen(
        [lmod_cmd, 'python', command] + list(
            arguments), stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = proc.communicate()
    err_out = sys.stderr
    if os.environ.get('LMOD_REDIRECT', 'yes') != 'no':
        err_out = sys.stdout

    print(stderr.decode(), file=err_out)
    exec(stdout.decode())
