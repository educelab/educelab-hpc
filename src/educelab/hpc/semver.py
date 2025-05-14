import re
from typing import Dict, Optional

_SEMVER_REGEX_STR = (R'(?P<major>0|[1-9]\d*)\.'
                     R'(?P<minor>0|[1-9]\d*)\.'
                     R'(?P<patch>0|[1-9]\d*)'
                     R'(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
                     R'(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?')
_SEMVER_REQ_REGEX_STR = R'(?P<requirement>[<>]=?|==)'

_SEMVER_REGEX = re.compile('^' + _SEMVER_REGEX_STR + '$')
_SEMVER_LOOSE_REGEX = re.compile(_SEMVER_REGEX_STR)
_SEMVER_REQ_REGEX = re.compile('^' + _SEMVER_REQ_REGEX_STR + _SEMVER_REGEX_STR + '$')


def _parse_version(s) -> Dict:
    res = re.search(_SEMVER_REGEX, s)
    if res is not None:
        res = res.groupdict()
        res['major'] = int(res['major'])
        res['minor'] = int(res['minor'])
        res['patch'] = int(res['patch'])
    return res


def _parse_version_requirement(s) -> Dict:
    res = re.search(_SEMVER_REQ_REGEX, s)
    if res is not None:
        res = res.groupdict()
        res['major'] = int(res['major'])
        res['minor'] = int(res['minor'])
        res['patch'] = int(res['patch'])
    return res


class Version:
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    buildmetadata: Optional[str] = None

    def __init__(self, version_str=None, major=None, minor=None, patch=None,
                 prerelease=None, buildmetadata=None, **kwargs):
        # TODO: Check that major, minor, etc aren't already set
        if version_str is not None:
            res = _parse_version(version_str)
            if res is None:
                raise ValueError(f'Could not parse version: {version_str}')
            major = res['major']
            minor = res['minor']
            patch = res['patch']
            prerelease = res['prerelease']
            buildmetadata = res['buildmetadata']

        # assign required
        self.major = major
        self.minor = minor
        self.patch = patch
        if self.is_null():
            return

        # assign extra
        self.prerelease = prerelease
        self.buildmetadata = buildmetadata

    def __str__(self):
        if self.is_null():
            return ''
        v = f'{self.major}.{self.minor}.{self.patch}'
        if self.prerelease is not None:
            v = f'{v}-{self.prerelease}'
        if self.buildmetadata is not None:
            v = f'{v}+{self.buildmetadata}'
        return v

    def __repr__(self):
        if self.is_null():
            return 'Version()'
        else:
            return f'Version(\'{self.__str__()}\')'

    def __eq__(self, other):
        # defer to VersionRequirement implementation
        if isinstance(other, VersionRequirement):
            return other == self

        if self.is_null() and other.is_null():
            return True

        if self.is_null() or other.is_null():
            raise RuntimeError(f"Cannot compare {repr(self)} to {repr(other)}")

        return self.major == other.major \
            and self.minor == other.minor \
            and self.patch == other.patch \
            and self.prerelease == other.prerelease

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if isinstance(other, VersionRequirement):
            raise RuntimeError(
                f"VersionRequirement only supports equality comparisons")

        # Not lt if eq
        if self.__eq__(other):
            return False

        # Compare version parts
        if self.major < other.major:
            return True
        if self.major > other.major:
            return False
        if self.minor < other.minor:
            return True
        if self.minor > other.minor:
            return False
        if self.patch < other.patch:
            return True
        if self.patch > other.patch:
            return False

        if self.prerelease is None:
            return False
        if self.prerelease is not None and other.prerelease is None:
            return True

        # compare parts of pre-release
        parts, parts_other = self.prerelease.split('.'), other.prerelease.split(
            '.')
        for a, b in zip(parts, parts_other):
            # if parts match, skip
            if a == b:
                continue

            # try to convert to int
            try:
                a = int(a)
            except ValueError:
                pass
            try:
                b = int(b)
            except ValueError:
                pass

            # compare as ints
            if isinstance(a, int) and isinstance(b, int):
                if a < b:
                    return True
                if b < a:
                    return False

            # string has precedence over int
            if isinstance(a, int) and isinstance(b, str):
                return True
            if isinstance(a, str) and isinstance(b, int):
                return False

            # string comparison
            if a < b:
                return True
            if b < a:
                return False

        # if all else fails, which one has more parts
        if len(parts) < len(parts_other):
            return True
        return False

    def __le__(self, other):
        if isinstance(other, VersionRequirement):
            raise RuntimeError(
                f"VersionRequirement only supports equality comparisons")
        return self.__eq__(other) or self.__lt__(other)

    def __gt__(self, other):
        if isinstance(other, VersionRequirement):
            raise RuntimeError(
                f"VersionRequirement only supports equality comparisons")
        return not self.__eq__(other) and not self.__lt__(other)

    def __ge__(self, other):
        if isinstance(other, VersionRequirement):
            raise RuntimeError(
                f"VersionRequirement only supports equality comparisons")
        return self.__eq__(other) or not self.__lt__(other)

    def is_null(self):
        return self.major is None or self.minor is None or self.patch is None


class VersionRequirement:
    min_requirement: str
    min_version: Version
    max_requirement: str = None
    max_version: Version = None

    def __init__(self, min_req, max_req: str = None, *args, **kwargs):
        # parse a single requirement
        res = _parse_version_requirement(min_req)
        if res is None:
            raise ValueError(f'Could not parse version requirement: {min_req}')
        self.min_requirement = res['requirement']
        self.min_version = Version(**res)

        if max_req is not None:
            res = _parse_version_requirement(max_req)
            if res is None:
                raise ValueError(
                    f'Could not parse version requirement: {max_req}')
            self.max_requirement = res['requirement']
            self.max_version = Version(**res)

            # double requirement can't contain ==
            if '==' in (self.min_requirement, self.max_requirement):
                raise ValueError(
                    f'Double requirement cannot include "==" requirement: {self.__str__()}')

            # swap double requirement order so that min is > and max is <
            min_less = self.min_requirement in ('<', '<=')
            max_greater = self.max_requirement in ('>', '>=')
            if min_less and max_greater:
                self.min_requirement, self.max_requirement = self.max_requirement, self.min_requirement
                self.min_version, self.max_version = self.max_version, self.min_version
            elif min_less or max_greater:
                raise ValueError(
                    f'Double requirement has matching signs: {self.__str__()}')

            # test that versions differ
            if self.min_version >= self.max_version:
                raise ValueError(
                    f'Min version must be less than max version: {self.__str__()}')

    def __str__(self):
        v = f'{self.min_requirement}{self.min_version}'
        if self.max_requirement is not None:
            v = f'{v},{self.max_requirement}{self.max_version}'
        return v

    def __repr__(self):
        return f'VersionRequirement(\'{self.__str__()}\')'

    def __eq__(self, other):
        if isinstance(other, VersionRequirement):
            raise RuntimeError(f"Cannot compare two VersionRequirements")

        if other is None or other.is_null():
            raise RuntimeError(
                f"Cannot compare {repr(other)} against {repr(self)}")

        meets_req = True
        if self.min_requirement == '==':
            meets_req = meets_req and other == self.min_version
        elif self.min_requirement == '<':
            meets_req = meets_req and other < self.min_version
        elif self.min_requirement == '<=':
            meets_req = meets_req and other <= self.min_version
        elif self.min_requirement == '>':
            meets_req = meets_req and other > self.min_version
        elif self.min_requirement == '>=':
            meets_req = meets_req and other >= self.min_version

        if meets_req and self.max_requirement is not None:
            if self.max_requirement == '<':
                meets_req = meets_req and other < self.max_version
            elif self.max_requirement == '<=':
                meets_req = meets_req and other <= self.max_version

        return meets_req

    def __ne__(self, other):
        return not self == other


def get_version(s: str) -> Optional[Version]:
    """Parse the first semver encountered in a string"""
    res = re.search(_SEMVER_LOOSE_REGEX, s)
    if res is not None:
        res = res.groupdict()
        res['major'] = int(res['major'])
        res['minor'] = int(res['minor'])
        res['patch'] = int(res['patch'])
        res = Version(**res)
    return res
