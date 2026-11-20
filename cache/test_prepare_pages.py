import unittest
from prepare_pages import select_release


class EditionOrderTests(unittest.TestCase):
    def test_select_by_source_time_and_reject_ambiguous_releases(self):
        older = dict(tag_name="osv-99-" + "0" * 16, immutable=True, draft=False, prerelease=False)
        newer = dict(older, tag_name="osv-100-" + "a" * 16)
        self.assertEqual(select_release([newer, older, dict(newer, immutable=False)]), newer["tag_name"])
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            select_release([newer, dict(newer, tag_name="osv-100-" + "b" * 16)])
