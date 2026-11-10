import dataclasses
import os
from pathlib import Path

import pytest

from educelab.hpc import profile as hpc_profile
from educelab.hpc.profile import ProfileError, load_profile, resolve_table

BASE = {'scratch_dir': '/scratch/proj', 'project_dir': '/project/proj',
        'cpu_account': 'cpu-acct', 'cpu_partition': 'cpu-part'}


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Keep the real user config and $EL_PROFILE out of every test."""
    # setenv first so teardown also undoes export_profile()'s write
    monkeypatch.setenv(hpc_profile.PROFILE_ENV_VAR, '')
    monkeypatch.delenv(hpc_profile.PROFILE_ENV_VAR)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg'))


def write_user_config(tmp_path, text):
    path = tmp_path / 'xdg' / 'educelab-hpc' / 'profiles.toml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def toml_table(name, keys):
    return f'[profiles.{name}]\n' + ''.join(
        f'{k} = "{v}"\n' for k, v in keys.items())


def profile_with(**keys):
    return load_profile('test', defaults={'profiles': {'test': {**BASE, **keys}}})


# --- selection --------------------------------------------------------------

TWO = {'active': 'a', 'profiles': {'a': BASE, 'b': BASE}}


def test_explicit_name_beats_environment(monkeypatch):
    monkeypatch.setenv('EL_PROFILE', 'a')
    assert load_profile('b', defaults=TWO).name == 'b'


def test_environment_beats_active_key(monkeypatch):
    monkeypatch.setenv('EL_PROFILE', 'b')
    assert load_profile(defaults=TWO).name == 'b'


def test_active_key_is_the_fallback():
    assert load_profile(defaults=TWO).name == 'a'


def test_no_selection_explains_how_to_choose():
    with pytest.raises(ProfileError, match='EL_PROFILE'):
        load_profile(defaults={'profiles': {'a': BASE}})


def test_unknown_profile_lists_available():
    with pytest.raises(ProfileError, match='Available profiles: a, b'):
        load_profile('nope', defaults=TWO)


def test_missing_required_keys_are_named():
    with pytest.raises(ProfileError, match='cpu_account, cpu_partition'):
        load_profile('x', defaults={'profiles': {'x': {
            'scratch_dir': '/s', 'project_dir': '/p'}}})


def test_profile_names():
    assert hpc_profile.profile_names(TWO) == ['a', 'b']


# --- inheritance ------------------------------------------------------------

LCC = {'cpu_partition': 'CAL48M192_L', 'gpu_partition': 'V4V32',
           'gpu_gres': 'gpu:1', 'apptainer_modules': ['ccs/singularity']}
HERC_LCC = {'inherits': 'lcc', 'scratch_dir': '/scratch/herc',
           'project_dir': '/project/herc', 'cpu_account': 'col_herc',
           'gpu_account': 'gol_herc'}
INHERITING = {'profiles': {'lcc': LCC, 'herc-lcc': HERC_LCC}}


def test_inherited_keys_are_extended_by_own_keys():
    p = load_profile('herc-lcc', defaults=INHERITING)
    assert p.cpu_partition == 'CAL48M192_L'
    assert p.apptainer_modules == ('ccs/singularity',)
    assert p.cpu_account == 'col_herc'
    assert p.sbatch_args(gpu=True) == [
        '-A', 'gol_herc', '-p', 'V4V32', '--gres=gpu:1']
    assert p.lineage == ('lcc', 'herc-lcc')
    assert 'inherits' not in p.extra


def test_child_overrides_parent():
    config = {'profiles': {'lcc': LCC, 'herc-lcc': {
        **HERC_LCC, 'gpu_gres': 'gpu:4', 'apptainer_modules': ['other/1']}}}
    p = load_profile('herc-lcc', defaults=config)
    assert p.gpu_gres == 'gpu:4'
    # Lists replace rather than append
    assert p.apptainer_modules == ('other/1',)


def test_a_profile_missing_required_keys_cannot_be_loaded():
    with pytest.raises(ProfileError, match='or on a profile it inherits'):
        load_profile('lcc', defaults=INHERITING)


def test_multi_level_inheritance():
    config = {'profiles': {
        'lcc': LCC, 'herc-lcc': HERC_LCC,
        'herc-lcc-test': {'inherits': 'herc-lcc', 'scratch_dir': '/tmp/t'}}}
    p = load_profile('herc-lcc-test', defaults=config)
    assert p.scratch_dir == Path('/tmp/t')
    assert p.cpu_account == 'col_herc'
    assert p.lineage == ('lcc', 'herc-lcc', 'herc-lcc-test')


def test_later_parents_override_earlier_ones():
    config = {'profiles': {
        'ecc': {'cpu_partition': 'ecc-part', 'gpu_gres': 'h100:1'},
        'herc': {**BASE, 'cpu_partition': 'herc-part', 'endpoint': 'herc-ep'},
        'herc-ecc': {'inherits': ['herc', 'ecc']}}}
    p = load_profile('herc-ecc', defaults=config)
    assert p.cpu_partition == 'ecc-part'
    assert p.gpu_gres == 'h100:1'
    assert p.extra['endpoint'] == 'herc-ep'
    assert p.lineage == ('herc', 'ecc', 'herc-ecc')


def test_a_diamond_ancestor_does_not_reoverride():
    # b overrides a's partition; c inherits a too, but must not restore it
    config = {'profiles': {
        'a': {**BASE, 'cpu_partition': 'from-a'},
        'b': {'inherits': 'a', 'cpu_partition': 'from-b'},
        'c': {'inherits': 'a', 'gpu_partition': 'from-c'},
        'd': {'inherits': ['b', 'c']}}}
    p = load_profile('d', defaults=config)
    assert p.cpu_partition == 'from-b'
    assert p.gpu_partition == 'from-c'
    assert p.lineage == ('a', 'b', 'c', 'd')


def test_nested_tables_merge_through_inheritance():
    config = {'profiles': {
        'a': {**BASE, 'env': {'X': '1', 'Y': '2'}},
        'b': {'inherits': 'a', 'env': {'Y': '3'}}}}
    assert dict(load_profile('b', defaults=config).extra['env']) == {
        'X': '1', 'Y': '3'}


def test_inheritance_cycle_is_reported():
    config = {'profiles': {'a': {**BASE, 'inherits': 'b'},
                           'b': {'inherits': 'a'}}}
    with pytest.raises(ProfileError, match='cycle: a -> b -> a'):
        load_profile('a', defaults=config)


def test_unknown_parent_is_reported():
    config = {'profiles': {'a': {**BASE, 'inherits': 'missing'}}}
    with pytest.raises(ProfileError, match='"a" inherits unknown profile'):
        load_profile('a', defaults=config)


def test_resolve_table_shows_the_merged_raw_values():
    table = resolve_table('herc-lcc', defaults=INHERITING)
    assert table['cpu_partition'] == 'CAL48M192_L'
    assert table['scratch_dir'] == '/scratch/herc'
    assert 'inherits' not in table


def test_user_tweak_reaches_inheriting_profiles(tmp_path):
    write_user_config(tmp_path, '[profiles.lcc]\ngpu_gres = "gpu:2"\n')
    assert load_profile('herc-lcc', defaults=INHERITING).gpu_gres == 'gpu:2'


def test_user_profile_can_inherit_a_shipped_one(tmp_path):
    write_user_config(tmp_path, 'active = "mine"\n' + toml_table('mine', {
        'inherits': 'lcc', 'scratch_dir': '/s', 'project_dir': '/p',
        'cpu_account': 'acct'}))
    p = load_profile(defaults={'profiles': {'lcc': LCC}})
    assert (p.name, p.cpu_partition) == ('mine', 'CAL48M192_L')


# --- config layering --------------------------------------------------------

def test_defaults_may_be_a_toml_file(tmp_path):
    path = tmp_path / 'profiles.toml'
    path.write_text('active = "f"\n' + toml_table('f', BASE))
    assert load_profile(defaults=path).name == 'f'
    assert load_profile(defaults=str(path)).name == 'f'


def test_user_config_merges_per_key_over_defaults(tmp_path):
    write_user_config(tmp_path, '[profiles.a]\ncpu_partition = "mine"\n')
    p = load_profile('a', defaults=TWO)
    assert p.cpu_partition == 'mine'
    assert p.cpu_account == 'cpu-acct'


def test_application_tables_are_merged_and_readable(tmp_path):
    write_user_config(tmp_path, '[deploy]\nhost = "user-host"\n')
    config = hpc_profile.load_config({'deploy': {'host': 'h', 'root': '/r'}})
    assert config['deploy'] == {'host': 'user-host', 'root': '/r'}


# --- resolution -------------------------------------------------------------

def test_paths_expand_env_vars_and_home(monkeypatch):
    monkeypatch.setenv('MY_SCRATCH', '/fast')
    p = profile_with(scratch_dir='$MY_SCRATCH/proj', project_dir='~/proj')
    assert p.scratch_dir == Path('/fast/proj')
    assert p.project_dir == Path.home() / 'proj'


def test_containers_dir_defaults_beneath_project_dir():
    assert profile_with().containers_dir == Path('/project/proj/containers')
    assert profile_with(containers_dir='/sif').containers_dir == Path('/sif')


def test_cpu_only_profile():
    p = profile_with()
    assert not p.has_gpu
    assert p.apptainer_modules == ()
    with pytest.raises(ProfileError, match='gpu_partition'):
        p.sbatch_args(gpu=True)


def test_gpu_account_defaults_to_cpu_account():
    assert profile_with(gpu_partition='g').gpu_account == 'cpu-acct'


def test_sbatch_args():
    p = profile_with(gpu_account='gpu-acct', gpu_partition='gpu-part',
                     gpu_gres='h100:1')
    assert p.sbatch_args() == ['-A', 'cpu-acct', '-p', 'cpu-part']
    assert p.sbatch_args(gpu=True) == [
        '-A', 'gpu-acct', '-p', 'gpu-part', '--gres=h100:1']


def test_modules_are_a_tuple_and_a_string_is_one_module():
    assert profile_with(apptainer_modules=['a/1', 'b/2']).apptainer_modules \
        == ('a/1', 'b/2')
    assert profile_with(apptainer_modules='ccs/singularity').apptainer_modules \
        == ('ccs/singularity',)


def test_load_apptainer_modules(monkeypatch):
    calls = []
    monkeypatch.setattr(hpc_profile, 'module', lambda *a: calls.append(a))
    profile_with().load_apptainer_modules()
    profile_with(apptainer_modules=['a/1', 'b/2']).load_apptainer_modules()
    assert calls == [('load', 'a/1', 'b/2')]


def test_unknown_keys_are_kept_in_extra(monkeypatch):
    monkeypatch.setenv('MY_PROJECT', '/p')
    p = profile_with(globus_endpoint='ep', configs_dir='$MY_PROJECT/cfg')
    assert dict(p.extra) == {'globus_endpoint': 'ep',
                             'configs_dir': '$MY_PROJECT/cfg'}
    assert p.extra_path('configs_dir') == Path('/p/cfg')
    assert p.extra_path('overlay_dir', Path()) == Path()


# --- immutability and side effects -------------------------------------------

def test_profile_is_frozen_and_hashable():
    p = profile_with(other='x')
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.scratch_dir = Path('/elsewhere')
    with pytest.raises(TypeError):
        p.extra['other'] = 'y'
    hash(p)


def test_replace_keeps_everything_else():
    p = profile_with(other='x')
    moved = dataclasses.replace(p, scratch_dir=Path('/tmp/s'))
    assert moved.scratch_dir == Path('/tmp/s')
    assert moved.extra == p.extra


def test_loading_has_no_side_effects(monkeypatch):
    monkeypatch.setenv('EL_PROFILE', 'a')
    load_profile('b', defaults=TWO)
    assert os.environ['EL_PROFILE'] == 'a'


def test_export_profile_round_trips():
    hpc_profile.export_profile(load_profile('b', defaults=TWO))
    assert os.environ['EL_PROFILE'] == 'b'
    assert load_profile(defaults=TWO).name == 'b'
