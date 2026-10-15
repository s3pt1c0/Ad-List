import unittest
from build import extract_domains, valid_domain

class BlocklistParserTests(unittest.TestCase):
    def test_domain_only(self):
        self.assertEqual(extract_domains("Ads.Example.COM"), ["ads.example.com"])

    def test_hosts_ipv4(self):
        self.assertEqual(extract_domains("0.0.0.0 ad.example.com tracker.example.com # comment"),
                         ["ad.example.com", "tracker.example.com"])

    def test_hosts_ipv6(self):
        self.assertEqual(extract_domains("::1 ad.example.com"), ["ad.example.com"])

    def test_adblock(self):
        self.assertEqual(extract_domains("||video.example.com^$third-party"), ["video.example.com"])

    def test_reject_adblock_exception(self):
        self.assertEqual(extract_domains("@@||example.com^"), [])

    def test_reject_adblock_path(self):
        self.assertEqual(extract_domains("||example.com/ad.js"), [])

    def test_reject_url_with_path(self):
        self.assertEqual(extract_domains("https://example.com/ads"), [])

    def test_reject_wildcard(self):
        self.assertEqual(extract_domains("*.example.com"), [])

    def test_reject_invalid(self):
        self.assertIsNone(valid_domain("localhost"))
        self.assertIsNone(valid_domain("0.0.0.0"))
        self.assertIsNone(valid_domain("-example.com"))
        self.assertIsNone(valid_domain("example..com"))

if __name__ == "__main__":
    unittest.main()
