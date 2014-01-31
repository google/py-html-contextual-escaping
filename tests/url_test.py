#!/usr/bin/env python -O

"""Testcases for module content"""

import escaping
import test_common
import unittest

class ContentTest(unittest.TestCase):
    """Testcases for module content"""

    def test_normalization(self):
        """Test URL normalization functions"""
        tests = (
            ("", ""),
            (
                "http://example.com:80/foo/bar?q=foo%20&bar=x+y#frag",
                "http://example.com:80/foo/bar?q=foo%20&bar=x+y#frag",
                ),
            (
                "http://example.com:80/foo/bar?q=foo &bar=x+y#frag",
                "http://example.com:80/foo/bar?q=foo%20&bar=x+y#frag",
                ),
            (" ", "%20"),
            ("%7c", "%7c"),
            ("%7C", "%7C"),
            # invalid escape sequences should be normalized.
            ("%2", "%252"),
            ("%", "%25"),
            ("%z", "%25z"),
            (u"/foo|bar/%5c\u1234", "/foo%7cbar/%5c%e1%88%b4"),
            ("<script>alert(1337)</script>",
             "%3cscript%3ealert%281337%29%3c/script%3e"),
            )
        for test_input, want in tests:
            got = escaping.normalize_url(test_input)
            self.assertEquals(want, got, test_input)
            self.assertEquals(want, escaping.normalize_url(want),
                              'idempotent %r' % want)

    def test_url_sanitizers(self):
        """Test escapers on selected codepoints"""

        test_input = test_common.ASCII_AND_SELECTED_CODEPOINTS

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
                 "%c2%a0%c4%80%e2%80%a8%e2%80%a9%ef%b7%ac%ef%bb%bf%f0%9d%84%9e"
                 ),
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
                 "%c2%a0%c4%80%e2%80%a8%e2%80%a9%ef%b7%ac%ef%bb%bf%f0%9d%84%9e"
                 ),
                ),
            )

        for sanitizer, want in tests:
            got = sanitizer(test_input)
            self.assertEquals(
                want, got,
                '%s\n\t%r\n!=\n\t%r' % (sanitizer.__name__, want, got))


if __name__ == '__main__':
    unittest.main()
