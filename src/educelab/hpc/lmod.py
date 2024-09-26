import os
import subprocess as sp
import sys


def module(command, *arguments):
    """For loading lmod modules, e.g. 'module load ccs/singularity'"""
    proc = sp.Popen(
        ['/opt/ohpc/admin/lmod/lmod/libexec/lmod', 'python', command] + list(
            arguments), stdout=sp.PIPE, stderr=sp.PIPE)
    stdout, stderr = proc.communicate()
    err_out = sys.stderr
    if os.environ.get('LMOD_REDIRECT', 'yes') != 'no':
        err_out = sys.stdout

    print(stderr.decode(), file=err_out)
    exec(stdout.decode())
