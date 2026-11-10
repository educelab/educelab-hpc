import os
from pathlib import Path
from typing import Optional


def _env_path(name: str) -> Optional[Path]:
    # Unset or empty is None, not Path(''), which would silently mean the cwd
    value = os.environ.get(name)
    return Path(value) if value else None


PROJECT = _env_path('PROJECT')
PSCRATCH = _env_path('PSCRATCH')
SCRATCH = _env_path('SCRATCH')
