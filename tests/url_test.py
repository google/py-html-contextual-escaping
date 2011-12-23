#!/usr/bin/python

"""Testcases for module content"""

import escaping
import unittest

class ContentTest(unittest.TestCase):
    """Testcases for module content"""

    def test_normalization(self):
        tests = (
            ("", ""),
            (
                "http://example.com:80/foo/bar?q=foo%20&bar=x+y#frag",
                "http://example.com:80/foo/bar?q=foo%20&bar=x+y#frag",
                ),
            (" ", "%20"),
            ("%7c", "%7c"),
            ("%7C", "%7C"),
            ("%2", "%252"),
            ("%", "%25"),
            ("%z", "%25z"),
            (u"/foo|bar/%5c\u1234", "/foo%7cbar/%5c%e1%88%b4"),
            )
        for test_input, want in tests:
            got = escaping.normalize_url(test_input)
            self.assertEquals(want, got, test_input)
            self.assertEquals(want, escaping.normalize_url(want),
                              'idempotent %r' % want)
    def test_url_sanitizers(self):
        test_input = (
            u"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f"
            u"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
            u" !\"#$%&'()*+,-./"
            u"0123456789:;<=>?"
            u"@ABCDEFGHIJKLMNO"
            u"PQRSTUVWXYZ[\\]^_"
            u"`abcdefghijklmno"
            u"pqrstuvwxyz{|}~\x7f"
            u"\u00A0\u0100\u2028\u2029\ufeff\U0001D11E")

        tests = (
            (
                escaping.escape_url,
                ("%00%01%02%03%04%05%06%07%08%09%0a%0b%0c%0d%0e%0f"
                 "%10%11%12%13%14%15%16%17%18%19%1a%1b%1c%1d%1e%1f"
                 "%20%21%22%23%24%25%26%27%28%29%2a%2b%2c-.%2f"
                 "0123456789%3a%3b%3c%3d%3e%3f"
                 "%40ABCDEFGHIJKLMNO"
                 "PQRSTUVWXYZ%5b%5c%5d%5e_"
                 "%60abcdefghijklmno"
                 "pqrstuvwxyz%7b%7c%7d~%7f"
                 "%c2%a0%c4%80%e2%80%a8%e2%80%a9%ef%bb%bf%f0%9d%84%9e"),
                ),
            (
                escaping.normalize_url,
                ("%00%01%02%03%04%05%06%07%08%09%0a%0b%0c%0d%0e%0f"
                 "%10%11%12%13%14%15%16%17%18%19%1a%1b%1c%1d%1e%1f"
                 "%20!%22#$%25&%27%28%29*+,-./"
                 "0123456789:;%3c=%3e?"
                 "@ABCDEFGHIJKLMNO"
                 "PQRSTUVWXYZ[%5c]%5e_"
                 "%60abcdefghijklmno"
                 "pqrstuvwxyz%7b%7c%7d~%7f"
                 "%c2%a0%c4%80%e2%80%a8%e2%80%a9%ef%bb%bf%f0%9d%84%9e"),
                  ),
            )

        for sanitizer, want in tests:
            got = sanitizer(test_input)
            self.assertEquals(
                want, got,
                '%s\n\t%r\n!=\n\t%r' % (sanitizer.__name__, want, got))


if __name__ == '__main__':
    unittest.main()
