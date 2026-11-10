"""Named, inheritable profiles of Slurm, module and filesystem settings.

Profiles are ``[profiles.<name>]`` TOML tables, layered from optional
application defaults and the user's ``profiles.toml``. The README covers the
config format, inheritance rules and selection order.
"""

import copy
import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from educelab.hpc.lmod import module

PROFILE_ENV_VAR = "EL_PROFILE"

Defaults = str | os.PathLike | Mapping[str, Any] | None

_INHERITS = "inherits"
_REQUIRED_KEYS = ("scratch_dir", "project_dir", "cpu_account", "cpu_partition")
_PATH_KEYS = ("scratch_dir", "project_dir", "containers_dir")
_STR_KEYS = ("cpu_account", "cpu_partition", "gpu_account", "gpu_partition", "gpu_gres")
_KNOWN_KEYS = _PATH_KEYS + _STR_KEYS + (_INHERITS, "apptainer_modules")
_UNSET_VAR = re.compile(r"\$(\w+|\{[^}]*\})")


class ProfileError(RuntimeError):
    """A profile could not be selected, resolved, or is invalid."""


def expand_path(path: str | os.PathLike) -> Path:
    """Expand ``~`` and environment variables (e.g. ``$PROJECT``) in a path.

    Raises `ProfileError` if the path names an unset variable, rather than
    leaving it in place as a literal, relative path.
    """
    expanded = os.path.expanduser(os.path.expandvars(str(path)))
    unset = _UNSET_VAR.findall(expanded)
    if unset:
        names = ", ".join("$" + v.strip("{}") for v in unset)
        raise ProfileError(f'"{path}" uses unset environment variable(s): {names}.')
    return Path(expanded)


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True)
class Profile:
    """A resolved profile, with inheritance applied and every path expanded.

    Profiles are immutable values, so one handed to several callers can't be
    re-pointed elsewhere. `lineage` lists the profiles merged to build this
    one, in merge order and ending with `name`. Keys the library doesn't
    recognize are kept, read-only, in `extra` for applications to interpret.
    """

    name: str
    scratch_dir: Path
    project_dir: Path
    containers_dir: Path  # defaults to <project_dir>/containers
    cpu_account: str
    cpu_partition: str
    gpu_account: str | None = None  # None means cpu_account
    gpu_partition: str | None = None
    gpu_gres: str | None = None
    apptainer_modules: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}), hash=False
    )

    def __post_init__(self):
        if self.gpu_account is None:
            object.__setattr__(self, "gpu_account", self.cpu_account)

    @property
    def has_gpu(self) -> bool:
        return self.gpu_partition is not None

    def sbatch_args(self, gpu: bool = False) -> list[str]:
        """Account, partition and (for GPU jobs) gres arguments for sbatch."""
        if not gpu:
            return ["-A", self.cpu_account, "-p", self.cpu_partition]
        if not self.has_gpu:
            raise ProfileError(f'Profile "{self.name}" has no gpu_partition.')
        args = ["-A", self.gpu_account, "-p", self.gpu_partition]
        if self.gpu_gres:
            args.append(f"--gres={self.gpu_gres}")
        return args

    def load_apptainer_modules(self) -> None:
        """Load the Lmod modules that provide apptainer for this profile."""
        if self.apptainer_modules:
            module("load", *self.apptainer_modules)

    def extra_path(self, key: str, default: Path | None = None) -> Path | None:
        """An application-defined path key from `extra`, expanded."""
        value = self.extra.get(key)
        return expand_path(value) if value else default


def user_config_path() -> Path:
    """The per-user config file, merged on top of any application defaults."""
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "educelab-hpc" / "profiles.toml"


def _load_toml(path: Path, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ProfileError(f"Profile defaults file not found: {path}")
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ProfileError(f"Invalid TOML in {path}: {e}") from e


def _merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge tables; any other value in `override` replaces."""
    merged = dict(base)
    for key, val in override.items():
        if isinstance(val, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_config(defaults: Defaults = None) -> dict[str, Any]:
    """The merged config: `defaults` with the user config on top.

    Inheritance is not applied here. Applications can keep their own top-level
    tables in the same file and read them from this.
    """
    if defaults is None:
        base = {}
    elif isinstance(defaults, Mapping):
        base = defaults
    else:
        base = _load_toml(Path(defaults), required=True)
    return copy.deepcopy(_merge(base, _load_toml(user_config_path())))


def _profiles(config: Mapping[str, Any]) -> Mapping[str, Any]:
    """The ``profiles`` table, checked to be a table of tables."""
    profiles = config.get("profiles", {})
    if not isinstance(profiles, Mapping):
        raise ProfileError('"profiles" must be a table of profiles.')
    for name, table in profiles.items():
        if not isinstance(table, Mapping):
            raise ProfileError(
                f'Profile "{name}" must be a table, not {type(table).__name__}.'
            )
    return profiles


def profile_names(defaults: Defaults = None) -> list[str]:
    """Names of every profile in the merged config."""
    return sorted(_profiles(load_config(defaults)))


def _parents(name: str, table: Mapping[str, Any]) -> tuple[str, ...]:
    value = table.get(_INHERITS, ())
    if isinstance(value, str):
        value = (value,)
    if not (
        isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value)
    ):
        raise ProfileError(
            f'Profile "{name}": inherits must be a profile name or a list of names.'
        )
    return tuple(v for v in value if v)


def _lineage(name: str, profiles: Mapping[str, Any]) -> list[str]:
    """Profiles in merge order: ancestors depth-first, then `name` itself.

    An ancestor reached twice (a diamond) is merged once, at its first
    position, so it can't re-override a profile that already overrode it.
    """
    order: list[str] = []

    def visit(current: str, stack: tuple[str, ...]):
        if current in stack:
            cycle = " -> ".join(stack[stack.index(current) :] + (current,))
            raise ProfileError(f"Profile inheritance cycle: {cycle}.")
        if current in order:
            return
        if current not in profiles:
            raise ProfileError(
                f'Profile "{stack[-1]}" inherits unknown profile "{current}".'
            )
        for parent in _parents(current, profiles[current]):
            visit(parent, stack + (current,))
        order.append(current)

    visit(name, ())
    return order


def _resolve(
    name: str, profiles: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none defined)"
        raise ProfileError(
            f'Unknown profile "{name}". Available profiles: {available}. '
            f"Define it in {user_config_path()}."
        )
    lineage = _lineage(name, profiles)
    table: dict[str, Any] = {}
    for ancestor in lineage:
        table = _merge(table, profiles[ancestor])
    table.pop(_INHERITS, None)
    # An empty string unsets an inherited key, since TOML has no null
    table = {k: v for k, v in table.items() if v != ""}
    return table, lineage


def resolve_table(name: str, defaults: Defaults = None) -> dict[str, Any]:
    """The raw, merged key/value table for profile `name`.

    Inheritance is applied but nothing is validated or expanded; useful for
    inspecting what a profile inherits.
    """
    return _resolve(name, _profiles(load_config(defaults)))[0]


def _check_types(name: str, table: Mapping[str, Any]) -> None:
    def fail(key, expected):
        raise ProfileError(
            f'Profile "{name}": {key} must be {expected}, not '
            f"{type(table[key]).__name__}."
        )

    for key in _STR_KEYS:
        if key in table and not isinstance(table[key], str):
            fail(key, "a string")
    for key in _PATH_KEYS:
        if key in table and not isinstance(table[key], (str, os.PathLike)):
            fail(key, "a path string")
    mods = table.get("apptainer_modules", ())
    if not (
        isinstance(mods, str)
        or (isinstance(mods, (list, tuple)) and all(isinstance(m, str) for m in mods))
    ):
        fail("apptainer_modules", "a module name or a list of names")


def load_profile(name: str | None = None, *, defaults: Defaults = None) -> Profile:
    """Resolve and load a profile.

    The profile is `name` if given, else ``$EL_PROFILE``, else the config's
    ``active`` key. Nothing is written, in particular not ``$EL_PROFILE``; use
    `export_profile()` for that.
    """
    config = load_config(defaults)
    name = name or os.environ.get(PROFILE_ENV_VAR) or config.get("active")
    if not name:
        raise ProfileError(
            f"No profile selected. Pass a profile name, set ${PROFILE_ENV_VAR}, "
            f'or add an "active" key to {user_config_path()}.'
        )

    table, lineage = _resolve(name, _profiles(config))
    missing = [k for k in _REQUIRED_KEYS if k not in table]
    if missing:
        raise ProfileError(
            f'Profile "{name}" is missing required keys: {", ".join(missing)}. '
            f"Set them on it or on a profile it inherits."
        )
    _check_types(name, table)

    def path(key):
        try:
            return expand_path(table[key])
        except ProfileError as e:
            raise ProfileError(f'Profile "{name}" {key}: {e}') from None

    project_dir = path("project_dir")
    mods = table.get("apptainer_modules", ())
    return Profile(
        name=name,
        scratch_dir=path("scratch_dir"),
        project_dir=project_dir,
        containers_dir=(
            path("containers_dir")
            if "containers_dir" in table
            else project_dir / "containers"
        ),
        cpu_account=table["cpu_account"],
        cpu_partition=table["cpu_partition"],
        gpu_account=table.get("gpu_account"),
        gpu_partition=table.get("gpu_partition"),
        gpu_gres=table.get("gpu_gres"),
        # A bare string is one module, not a sequence of characters
        apptainer_modules=(mods,) if isinstance(mods, str) else tuple(mods),
        lineage=tuple(lineage),
        extra=_freeze({k: v for k, v in table.items() if k not in _KNOWN_KEYS}),
    )


def export_profile(profile: Profile) -> None:
    """Set ``$EL_PROFILE`` so jobs queued from this process select `profile`.

    ``sbatch --export=ALL`` (Slurm's default) forwards only the name. The job
    resolves it again, so it must pass `load_profile()` the same `defaults`,
    and it reads the user config as it is when the job starts.
    """
    os.environ[PROFILE_ENV_VAR] = profile.name
