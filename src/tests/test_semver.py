import unittest

from educelab.hpc.semver import Version, VersionRequirement


class TestVersion(unittest.TestCase):
    def test_init_args(self):
        v = Version(major=1, minor=0, patch=0, prerelease='alpha1',
                    buildmetadata='test')
        self.assertEqual(str(v), '1.0.0-alpha1+test')

    def test_init_str(self):
        v = Version('1.0.0-alpha1+test')
        self.assertEqual(str(v), '1.0.0-alpha1+test')
        self.assertRaises(ValueError, Version, 'bad')
        self.assertRaises(ValueError, Version, '1')
        self.assertRaises(ValueError, Version, '1.0')
        self.assertRaises(ValueError, Version, 'bad-1.0.0')

    def test_version_eq(self):
        self.assertEqual(Version(), Version())
        self.assertEqual(Version('1.0.0'), Version('1.0.0'))
        self.assertNotEqual(Version('1.0.0'), Version('1.1.0'))

    def test_version_lt(self):
        l = Version('1.0.0')
        h = Version('1.1.0')
        self.assertTrue(l < h)
        self.assertFalse(h < l)

    def test_version_lte(self):
        l = Version('1.0.0')
        s = Version('1.0.0')
        h = Version('1.1.0')
        self.assertTrue(l <= h)
        self.assertTrue(l <= s)
        self.assertFalse(h <= l)
        self.assertFalse(h <= s)

    def test_version_gt(self):
        l = Version('1.0.0')
        h = Version('1.1.0')
        self.assertTrue(h > l)
        self.assertFalse(l > h)

    def test_version_gte(self):
        l = Version('1.0.0')
        s = Version('1.1.0')
        h = Version('1.1.0')
        self.assertFalse(l >= h)
        self.assertFalse(l >= s)
        self.assertTrue(h >= l)
        self.assertTrue(h >= s)


class TestVersionRequirement(unittest.TestCase):
    def test_init_str(self):
        for r in ('==', '<', '<=', '>', '>='):
            v = VersionRequirement(f'{r}1.0.0-alpha1+test')
            self.assertEqual(str(v), f'{r}1.0.0-alpha1+test')
        self.assertRaises(ValueError, Version, 'bad')
        self.assertRaises(ValueError, Version, '1')
        self.assertRaises(ValueError, Version, '1.0')
        self.assertRaises(ValueError, Version, 'bad-1.0.0')

    def test_cant_compare_requirements(self):
        self.assertRaises(RuntimeError, lambda a, b: a == b,
                          VersionRequirement('>1.0.0'),
                          VersionRequirement('<1.0.0'))

    def test_req1_eq(self):
        self.assertTrue(Version('1.1.0') == VersionRequirement('==1.1.0'))
        self.assertTrue(VersionRequirement('==1.1.0') == Version('1.1.0'))

        self.assertFalse(Version('1.0.0') == VersionRequirement('==1.1.0'))
        self.assertFalse(VersionRequirement('==1.1.0') == Version('1.0.0'))

    def test_req1_lt(self):
        self.assertTrue(Version('1.0.0') == VersionRequirement('<1.1.0'))
        self.assertTrue(VersionRequirement('<1.1.0') == Version('1.0.0'))

        self.assertFalse(Version('1.2.0') == VersionRequirement('<1.1.0'))
        self.assertFalse(VersionRequirement('<1.1.0') == Version('1.2.0'))

    def test_req1_lte(self):
        self.assertTrue(Version('1.0.0') == VersionRequirement('<=1.1.0'))
        self.assertTrue(VersionRequirement('<=1.1.0') == Version('1.0.0'))
        self.assertTrue(Version('1.1.0') == VersionRequirement('<=1.1.0'))
        self.assertTrue(VersionRequirement('<=1.1.0') == Version('1.1.0'))

        self.assertFalse(Version('1.2.0') == VersionRequirement('<=1.1.0'))
        self.assertFalse(VersionRequirement('<=1.1.0') == Version('1.2.0'))

    def test_req1_gt(self):
        self.assertTrue(Version('1.2.0') == VersionRequirement('>1.1.0'))
        self.assertTrue(VersionRequirement('>1.1.0') == Version('1.2.0'))

        self.assertFalse(Version('1.0.0') == VersionRequirement('>1.1.0'))
        self.assertFalse(VersionRequirement('>1.1.0') == Version('1.0.0'))

    def test_req1_gte(self):
        self.assertTrue(Version('1.1.0') == VersionRequirement('>=1.1.0'))
        self.assertTrue(VersionRequirement('>=1.1.0') == Version('1.1.0'))
        self.assertTrue(Version('1.2.0') == VersionRequirement('>=1.1.0'))
        self.assertTrue(VersionRequirement('>=1.1.0') == Version('1.2.0'))

        self.assertFalse(Version('1.0.0') == VersionRequirement('>=1.1.0'))
        self.assertFalse(VersionRequirement('>=1.1.0') == Version('1.0.0'))

    def test_other_comparisons(self):
        self.assertRaises(RuntimeError, lambda a, b: a < b, Version('1.0.0'),
                          VersionRequirement('<1.1.0'))
        self.assertRaises(RuntimeError, lambda a, b: a <= b, Version('1.0.0'),
                          VersionRequirement('<1.1.0'))
        self.assertRaises(RuntimeError, lambda a, b: b < a, Version('1.0.0'),
                          VersionRequirement('<1.1.0'))
        self.assertRaises(RuntimeError, lambda a, b: b <= a, Version('1.0.0'),
                          VersionRequirement('<1.1.0'))

    def test_req2_init(self):
        self.assertEqual(str(VersionRequirement('>1.0.0', '<2.0.0')),
                         '>1.0.0,<2.0.0')
        self.assertEqual(str(VersionRequirement('<2.0.0', '>1.0.0')),
                         '>1.0.0,<2.0.0')

    def test_req2_bad_init(self):
        self.assertRaises(ValueError, VersionRequirement, '>1.0.0', '<1.1')
        self.assertRaises(ValueError, VersionRequirement, '==1.0.0', '<1.1.0')
        self.assertRaises(ValueError, VersionRequirement, '>1.0.0', '==1.1.0')
        self.assertRaises(ValueError, VersionRequirement, '<1.0.0', '<1.1.0')
        self.assertRaises(ValueError, VersionRequirement, '>1.0.0', '>1.1.0')
        self.assertRaises(ValueError, VersionRequirement, '>1.0.0', '<1.0.0')
        self.assertRaises(ValueError, VersionRequirement, '>=1.0.0', '<1.0.0')
        self.assertRaises(ValueError, VersionRequirement, '>2.0.0', '<1.0.0')

    def test_req2_gt_lt(self):
        req = VersionRequirement('>1.0.0', '<1.1.0')
        self.assertTrue(Version('1.0.5') == req)
        self.assertTrue(req == Version('1.0.5'))

        self.assertFalse(Version('1.0.0') == req)
        self.assertFalse(req == Version('1.0.0'))
        self.assertFalse(Version('1.1.0') == req)
        self.assertFalse(req == Version('1.1.0'))

    def test_req2_gte_lt(self):
        req = VersionRequirement('>=1.0.0', '<1.1.0')
        self.assertTrue(Version('1.0.0') == req)
        self.assertTrue(req == Version('1.0.0'))
        self.assertTrue(Version('1.0.5') == req)
        self.assertTrue(req == Version('1.0.5'))

        self.assertFalse(Version('0.9.0') == req)
        self.assertFalse(req == Version('0.9.0'))
        self.assertFalse(Version('1.1.0') == req)
        self.assertFalse(req == Version('1.1.0'))

    def test_req2_gt_lte(self):
        req = VersionRequirement('>1.0.0', '<=1.1.0')
        self.assertTrue(Version('1.0.5') == req)
        self.assertTrue(req == Version('1.0.5'))
        self.assertTrue(Version('1.1.0') == req)
        self.assertTrue(req == Version('1.1.0'))

        self.assertFalse(Version('1.0.0') == req)
        self.assertFalse(req == Version('1.0.0'))
        self.assertFalse(Version('1.2.0') == req)
        self.assertFalse(req == Version('1.2.0'))

    def test_req2_gte_lte(self):
        req = VersionRequirement('>=1.0.0', '<=1.1.0')
        self.assertTrue(Version('1.0.0') == req)
        self.assertTrue(req == Version('1.0.0'))
        self.assertTrue(Version('1.0.5') == req)
        self.assertTrue(req == Version('1.0.5'))
        self.assertTrue(Version('1.1.0') == req)
        self.assertTrue(req == Version('1.1.0'))

        self.assertFalse(Version('0.9.0') == req)
        self.assertFalse(req == Version('0.9.0'))
        self.assertFalse(Version('1.2.0') == req)
        self.assertFalse(req == Version('1.2.0'))


if __name__ == '__main__':
    unittest.main()
