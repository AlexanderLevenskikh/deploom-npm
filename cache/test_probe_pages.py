import unittest
from probe_pages import check_freshness


class FreshnessTests(unittest.TestCase):
    def test_expiry_boundaries(self):
        m = {"published": 1_000_000, "expires": 1_604_800}
        check_freshness(m, m["published"])
        check_freshness(m, m["expires"] - 2 * 86400 - 1)
        for now, message in [(m["expires"] - 2 * 86400, "within"), (m["expires"], "has expired"),
                             (m["published"] - 301, "Invalid")]:
            with self.subTest(now=now), self.assertRaisesRegex(ValueError, message):
                check_freshness(m, now)
        with self.assertRaisesRegex(ValueError, "Invalid"):
            check_freshness(dict(m, expires=m["expires"] + 1), m["published"])
