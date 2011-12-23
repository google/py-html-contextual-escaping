#!/usr/bin/python

"""Testcases for module html"""

import content
import escaping
import html
import test_common
import unittest

class HtmlTest(unittest.TestCase):
    """Testcases for module html"""

    def test_unescape_html(self):
        """
        Test unescape_html on corner cases like supplemental codepoints,
        re-escaping, broken escapes, etc.
        """
        self.assertEquals('', html.unescape_html(''))
        self.assertEquals('foo', html.unescape_html('foo'))
        self.assertEquals('foo<bar', html.unescape_html('foo&lt;bar'))
        self.assertEquals('foo< bar', html.unescape_html('foo&lt bar'))
        self.assertEquals('foo&amp;bar', html.unescape_html('foo&amp;amp;bar'))
        self.assertEquals('foo&bogus;bar', html.unescape_html('foo&bogus;bar'))
        self.assertEquals(
            u'>>>\u226b&gt;', html.unescape_html('&gt&gt;&GT;&Gt;&amp;gt;'))
        self.assertEquals(
            '""""', html.unescape_html('&#34;&#x22;&#X22;&quot;'))
        self.assertEquals(
            '<<<<', html.unescape_html('&#60;&#x3c;&#X3C;&lt;'))
        self.assertEquals(
            u'\u1234\u1234', html.unescape_html('&#4660;&#x1234;'))
        self.assertEquals(
            u'\uabcd\uabcd', html.unescape_html('&#43981;&#xabcd;'))
        self.assertEquals(
            u"\U0001D11E\U0001D11E",
            html.unescape_html('&#x1d11e;&#xd834;&#xdd1e;'))
        self.assertEquals("&#;&#gt;&#xxa0;", "&#;&#gt;&#xxa0;")

    def test_escape_html(self):
        """Test escape HTML on selected codepoints."""
        test_input = test_common.ASCII_AND_SELECTED_CODEPOINTS

        want = (
            u'&#xfffd;\x01\x02\x03\x04\x05\x06\x07'
            u'\x08\t\n\x0B\x0C\r\x0E\x0F'
            u'\x10\x11\x12\x13\x14\x15\x16\x17'
            u'\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f'
            u' !&#34;#$%&amp;&#39;()*&#43;,-./'
            u'0123456789:;&lt;=&gt;?'
            u'@ABCDEFGHIJKLMNO'
            u'PQRSTUVWXYZ[\]^_'
            u'&#96;abcdefghijklmno'
            u'pqrstuvwxyz{|}~\x7f'
            u'\u00A0\u0100\u2028\u2029\ufdec\ufeff\U0001D11E')

        got = escaping.escape_html(test_input)
        self.assertEquals(
            want, got, 'escaped:\n\t%r\n!=\n\t%r' % (want, got))
        want, got = u'\ufffd%s' % test_input[1:], html.unescape_html(got)
        self.assertEquals(
            want, got, 'reversible:\n\t%r\n!=\n\t%r' % (want, got))

    def test_strip_tags(self):
        """
        Test the tag stripper that is used to embed known safe HTML content
        in attribute values after removing tags.
        """
        tests = (
            ("", ""),
            ("Hello, World!", "Hello, World!"),
            ("foo&amp;bar", "foo&amp;bar"),
            ('Hello <a href="www.example.com/">World</a>!', "Hello World!"),
            ("Foo <textarea>Bar</textarea> Baz", "Foo Bar Baz"),
            ("Foo <!-- Bar --> Baz", "Foo  Baz"),
            ("<", "&lt;"),
            ("foo < bar", "foo &lt; bar"),
            ('Foo<script type="text/javascript">alert(1337)</script>Bar',
             "Fooalert(1337)Bar"  # Or "FooBar" would be better
             ),
            ('Foo<div title="1>2">Bar', "FooBar"),
            ('I <3 Ponies!', 'I &lt;3 Ponies!'),
            ('<script>foo()</script>', 'foo()'),  # Or ''
            )

        for test_input, want in tests:
            got = escaping.escape_html_attribute(content.SafeHTML(test_input))
            self.assertEquals(
                want, got, '%s:\n\t%r\n!=\n\t%r' % (test_input, want, got))

    def test_filter_html_attr(self):
        """Tests normalization of HTML attr values"""
        tests = (
            (
                content.SafeHTMLAttr(' dir=ltr'),
                ' dir="ltr"',
                ),
            (
                content.SafeHTMLAttr('dir="ltr"'),
                ' dir="ltr"',
                ),
            (
                content.SafeHTMLAttr("dir='ltr'"),
                ' dir="ltr"',
                ),
            (
                content.SafeHTMLAttr("title=foo \"bar &amp; <baz>'"),
                ' title="foo &#34;bar &amp; &lt;baz&gt;"',
                ),
            (
                content.SafeHTMLAttr(">"),
                '',
                ),
            (
                # The value should be trusted.
                content.SafeHTMLAttr("href = javascript:alert(1337) "),
                ' href="javascript:alert(1337)"',
                ),
            (
                # A generic attr name can be emitted.
                'title',
                'title',
                ),
            (
                # but privileged ones cannot.
                'style',
                'zSafehtmlz',
                ),
            (
                'Style',
                'zSafehtmlz',
                ),
            (
                'href',
                'zSafehtmlz',
                ),
            (
                ' HREF ',
                'zSafehtmlz',
                ),
            (
                'crossorigin',
                'zSafehtmlz',
                ),
            )
        for test_input, want in tests:
            got = escaping.filter_html_attribute(test_input)
            self.assertEquals(want, got)
        

if __name__ == '__main__':
    unittest.main()
