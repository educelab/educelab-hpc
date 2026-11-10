"""Named profiles of Slurm, module and filesystem settings, loaded from TOML.

Profiles live under ``[profiles.<name>]`` tables. Any profile may inherit from
any others with ``inherits = "lcc"`` or ``inherits = ["lcc", "herc"]``, then
add or override keys::

    [profiles.lcc]
    cpu_partition = "CAL48M192_L"
    apptainer_modules = ["ccs/singularity"]

    [profiles.herc-lcc]
    inherits = "lcc"
    cpu_account = "col_seales_uksr"
    ...

Parents apply in order, so later parents override earlier ones and the
profile's own keys override them all. Tables merge key by key; any other value,
lists included, replaces what it inherits.

An application may supply its own defaults (a path or dict), and the user
config at ``$XDG_CONFIG_HOME/educelab-hpc/profiles.toml`` (default
``~/.config/...``) is merged on top of them *before* inheritance is resolved, so
a user tweak to a profile reaches every profile inheriting from it.

The profile is chosen by, highest precedence first: an explicit name, the
``$EL_PROFILE`` environment variable, or the config's top-level ``active`` key.
Loading has no side effects. A submitter that wants its Slurm jobs to resolve
the same profile calls `export_profile()`, and ``sbatch --export=ALL`` forwards
the variable.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from educelab.hpc.lmod import module

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

PROFILE_ENV_VAR = 'EL_PROFILE'

Defaults = Union[str, os.PathLike, Mapping[str, Any], None]

_INHERITS = 'inherits'
_REQUIRED_KEYS = ('scratch_dir', 'project_dir', 'cpu_account', 'cpu_partition')
_KNOWN_KEYS = _REQUIRED_KEYS + (
    _INHERITS, 'gpu_account', 'gpu_partition', 'gpu_gres', 'apptainer_modules',
    'containers_dir')


class ProfileError(RuntimeError):
    """A profile could not be selected, resolved, or is incomplete."""


def expand_path(path: Union[str, os.PathLike]) -> Path:
    """Expand ``~`` and environment variables (e.g. ``$PROJECT``) in a path."""
    return Path(os.path.expanduser(os.path.expandvars(str(path))))


@dataclass(frozen=True)
class Profile:
    """A resolved profile, with inheritance applied and every path expanded.

    Profiles are immutable values, so one handed to several callers can't be
    re-pointed elsewhere. `lineage` lists the profiles merged to build this
    one, in merge order and ending with `name`. Keys the library doesn't recognize
    are kept, read-only, in `extra` for applications to interpret.
    """
    name: str
    scratch_dir: Path
    project_dir: Path
    containers_dir: Path  # defaults to <project_dir>/containers
    cpu_account: str
    cpu_partition: str
    gpu_account: Optional[str] = None  # defaults to cpu_account when loaded
    gpu_partition: Optional[str] = None
    gpu_gres: Optional[str] = None
    apptainer_modules: Tuple[str, ...] = ()
    lineage: Tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}), hash=False)

    @property
    def has_gpu(self) -> bool:
        return self.gpu_partition is not None

    def sbatch_args(self, gpu: bool = False) -> List[str]:
        """Account, partition and (for GPU jobs) gres arguments for sbatch."""
        if not gpu:
            return ['-A', self.cpu_account, '-p', self.cpu_partition]
        if not self.has_gpu:
            raise ProfileError(f'Profile "{self.name}" has no gpu_partition.')
        args = ['-A', self.gpu_account or self.cpu_account,
                '-p', self.gpu_partition]
        if self.gpu_gres:
            args.append(f'--gres={self.gpu_gres}')
        return args

    def load_apptainer_modules(self) -> None:
        """Load the Lmod modules that provide apptainer for this profile."""
        if self.apptainer_modules:
            module('load', *self.apptainer_modules)

    def extra_path(self, key: str,
                   default: Optional[Path] = None) -> Optional[Path]:
        """An application-defined path key from `extra`, expanded."""
        value = self.extra.get(key)
        return expand_path(value) if value else default


def user_config_path() -> Path:
    """The per-user config file, merged on top of any application defaults."""
    base = os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config')
    return Path(base) / 'educelab-hpc' / 'profiles.toml'


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, 'rb') as f:
        return tomllib.load(f)


def _merge(base: Mapping[str, Any],
           override: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge tables; any other value in `override` replaces."""
    merged = dict(base)
    for key, val in override.items():
        if isinstance(val, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_config(defaults: Defaults = None) -> Dict[str, Any]:
    """The merged config: `defaults` with the user config on top.

    Inheritance is not applied here. Applications can keep their own top-level
    tables in the same file and read them from this.
    """
    if defaults is None:
        base = {}
    elif isinstance(defaults, Mapping):
        base = defaults
    else:
        base = _load_toml(Path(defaults))
    return _merge(base, _load_toml(user_config_path()))


def profile_names(defaults: Defaults = None) -> List[str]:
    """Names of every profile in the merged config."""
    return sorted(load_config(defaults).get('profiles', {}))


def _as_tuple(value) -> Tuple[str, ...]:
    # A bare string is one item, not a sequence of single characters
    return (value,) if isinstance(value, str) else tuple(value)


def _lineage(name: str, profiles: Mapping[str, Any]) -> List[str]:
    """Profiles in merge order: ancestors depth-first, then `name` itself.

    An ancestor reached twice (a diamond) is merged once, at its first
    position, so it can't re-override a profile that already overrode it.
    """
    order: List[str] = []

    def visit(current: str, stack: Tuple[str, ...]):
        if current in stack:
            cycle = ' -> '.join(stack[stack.index(current):] + (current,))
            raise ProfileError(f'Profile inheritance cycle: {cycle}.')
        if current not in profiles:
            raise ProfileError(
                f'Profile "{stack[-1]}" inherits unknown profile "{current}".')
        for parent in _as_tuple(profiles[current].get(_INHERITS, ())):
            visit(parent, stack + (current,))
        if current not in order:
            order.append(current)

    visit(name, ())
    return order


def _resolve(name: str, profiles: Mapping[str, Any]
             ) -> Tuple[Dict[str, Any], List[str]]:
    if name not in profiles:
        available = ', '.join(sorted(profiles)) or '(none defined)'
        raise ProfileError(
            f'Unknown profile "{name}". Available profiles: {available}. '
            f'Define it in {user_config_path()}.')
    lineage = _lineage(name, profiles)
    table: Dict[str, Any] = {}
    for ancestor in lineage:
        table = _merge(table, profiles[ancestor])
    table.pop(_INHERITS, None)
    return table, lineage


def resolve_table(name: str, defaults: Defaults = None) -> Dict[str, Any]:
    """The raw, merged key/value table for profile `name`.

    Inheritance is applied but nothing is validated or expanded; useful for
    inspecting what a profile inherits.
    """
    return _resolve(name, load_config(defaults).get('profiles', {}))[0]


def load_profile(name: Optional[str] = None, *,
                 defaults: Defaults = None) -> Profile:
    """Resolve and load a profile.

    The profile is `name` if given, else ``$EL_PROFILE``, else the config's
    ``active`` key. Nothing is written, in particular not ``$EL_PROFILE``; use
    `export_profile()` for that.
    """
    config = load_config(defaults)
    name = name or os.environ.get(PROFILE_ENV_VAR) or config.get('active')
    if not name:
        raise ProfileError(
            f'No profile selected. Pass a profile name, set ${PROFILE_ENV_VAR}, '
            f'or add an "active" key to {user_config_path()}.')

    table, lineage = _resolve(name, config.get('profiles', {}))
    missing = [k for k in _REQUIRED_KEYS if k not in table]
    if missing:
        raise ProfileError(
            f'Profile "{name}" is missing required keys: {", ".join(missing)}. '
            f'Set them on it or on a profile it inherits.')

    project_dir = expand_path(table['project_dir'])
    containers_dir = table.get('containers_dir')
    return Profile(
        name=name,
        scratch_dir=expand_path(table['scratch_dir']),
        project_dir=project_dir,
        containers_dir=(expand_path(containers_dir) if containers_dir
                        else project_dir / 'containers'),
        cpu_account=table['cpu_account'],
        cpu_partition=table['cpu_partition'],
        gpu_account=table.get('gpu_account', table['cpu_account']),
        gpu_partition=table.get('gpu_partition'),
        gpu_gres=table.get('gpu_gres'),
        apptainer_modules=_as_tuple(table.get('apptainer_modules', ())),
        lineage=tuple(lineage),
        extra=MappingProxyType(
            {k: v for k, v in table.items() if k not in _KNOWN_KEYS}),
    )


def export_profile(profile: Profile) -> None:
    """Set ``$EL_PROFILE`` so jobs queued from this process load `profile`.

    ``sbatch --export=ALL`` (Slurm's default) forwards it, and a bare
    `load_profile()` inside the job reads it back.
    """
    os.environ[PROFILE_ENV_VAR] = profile.name
