import os
from pathlib import Path

PROJECT = Path(os.environ.get('PROJECT', ''))
PSCRATCH = Path(os.environ.get('PSCRATCH', ''))
SCRATCH = Path(os.environ.get('SCRATCH', ''))
