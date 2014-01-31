#!/usr/bin/env python -O

"""Testcases for module content"""

import content
import escape
import template
import unittest

class ContentTest(unittest.TestCase):
    """Testcases for module content"""

    def test_typed_content(self):
        """Test rendering and normalization of typed content by escapers."""
        data = (
            '<b> "foo%" O\'Reilly &bar;',
            content.SafeCSS('a[href =~ "//example.com"]#foo'),
            content.SafeHTML('Hello, <b>World</b> &amp;tc!'),
            content.SafeHTMLAttr(' dir="ltr"'),
            content.SafeJS('c && alert("Hello, World!");'),
            content.SafeJSStr('Hello, World & O\'Reilly\\x21'),
            content.SafeURL('greeting=H%69&addressee=(World)'),
            )

        # For each content sensitive escaper, see how it does on
        # each of the typed strings above.
        tests = (
            (
                '<style>{{.}} { color: blue }</style>',
                (
                    'zSafehtmlz',
                    # Allowed but not escaped.
                    'a[href =~ "//example.com"]#foo',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    ),
                ),
            (
                '<div style="{{.}}">',
                (
                    'zSafehtmlz',
                    # Allowed and HTML escaped.
                    'a[href =~ &#34;//example.com&#34;]#foo',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    ),
                ),
            (
                '{{.}}',
                (
                    '&lt;b&gt; &#34;foo%&#34; O&#39;Reilly &amp;bar;',
                    'a[href =~ &#34;//example.com&#34;]#foo',
                    # Not escaped.
                    'Hello, <b>World</b> &amp;tc!',
                    ' dir=&#34;ltr&#34;',
                    'c &amp;&amp; alert(&#34;Hello, World!&#34;);',
                    r'Hello, World &amp; O&#39;Reilly\x21',
                    'greeting=H%69&amp;addressee=(World)',
                    ),
                ),
            (
                '<a{{.}}>',
                (
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    # Allowed and HTML escaped.
                    ' dir="ltr"',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    'zSafehtmlz',
                    ),
                ),
            (
                '<a title={{.}}>',
                (
                    '"&lt;b&gt; &#34;foo%&#34; O&#39;Reilly &amp;bar;"',
                    '"a[href =~ &#34;//example.com&#34;]#foo"',
                    # Tags stripped, spaces escaped, entity not re-escaped.
                    '"Hello, World &amp;tc!"',
                    '" dir=&#34;ltr&#34;"',
                    '"c &amp;&amp; alert(&#34;Hello, World!&#34;);"',
                    r'"Hello, World &amp; O&#39;Reilly\x21"',
                    '"greeting=H%69&amp;addressee=(World)"',
                    ),
                ),
            (
                "<a title='{{.}}'>",
                (
                    '&lt;b&gt; &#34;foo%&#34; O&#39;Reilly &amp;bar;',
                    'a[href =~ &#34;//example.com&#34;]#foo',
                    # Tags stripped, entity not re-escaped.
                    'Hello, World &amp;tc!',
                    ' dir=&#34;ltr&#34;',
                    'c &amp;&amp; alert(&#34;Hello, World!&#34;);',
                    r'Hello, World &amp; O&#39;Reilly\x21',
                    'greeting=H%69&amp;addressee=(World)',
                    ),
                ),
            (
                '<textarea>{{.}}</textarea>',
                (
                    '&lt;b&gt; &#34;foo%&#34; O&#39;Reilly &amp;bar;',
                    'a[href =~ &#34;//example.com&#34;]#foo',
                    # Angle brackets escaped to prevent injection of close
                    # tags, entity not re-escaped.
                    'Hello, &lt;b&gt;World&lt;/b&gt; &amp;tc!',
                    ' dir=&#34;ltr&#34;',
                    'c &amp;&amp; alert(&#34;Hello, World!&#34;);',
                    r'Hello, World &amp; O&#39;Reilly\x21',
                    'greeting=H%69&amp;addressee=(World)',
                    ),
                ),
            (
                '<script>alert({{.}})</script>',
                (
                    '"\\x3cb\\x3e \\"foo%\\" O\'Reilly &bar;"',
                    r'"a[href =~ \"//example.com\"]#foo"',
                    r'"Hello, \x3cb\x3eWorld\x3c/b\x3e &amp;tc!"',
                    r'" dir=\"ltr\""',
                    # Not escaped.
                    'c && alert("Hello, World!");',
                    # Escape sequence not over-escaped.
                    '"Hello, World \\x26 O\\x27Reilly\\x21"',
                    '"greeting=H%69&addressee=(World)"',
                    ),
                ),
            (
                '<button onclick="alert({{.}})">',
                (
                    (r'&#34;\x3cb\x3e \&#34;foo%\&#34;'
                     r' O&#39;Reilly &amp;bar;&#34;'),
                    r'&#34;a[href =~ \&#34;//example.com\&#34;]#foo&#34;',
                    r'&#34;Hello, \x3cb\x3eWorld\x3c/b\x3e &amp;amp;tc!&#34;',
                    r'&#34; dir=\&#34;ltr\&#34;&#34;',
                    # Not JS escaped but HTML escaped.
                    r'c &amp;&amp; alert(&#34;Hello, World!&#34;);',
                    # Escape sequence not over-escaped.
                    r'&#34;Hello, World \x26 O\x27Reilly\x21&#34;',
                    r'&#34;greeting=H%69&amp;addressee=(World)&#34;',
                    ),
                ),
            (
                '<script>alert("{{.}}")</script>',
                (
                    r'\x3cb\x3e \x22foo%\x22 O\x27Reilly \x26bar;',
                    r'a[href \x3d~ \x22\/\/example.com\x22]#foo',
                    r'Hello, \x3cb\x3eWorld\x3c\/b\x3e \x26amp;tc!',
                    r' dir\x3d\x22ltr\x22',
                    r'c \x26\x26 alert(\x22Hello, World!\x22);',
                    # Escape sequence not over-escaped.
                    r'Hello, World \x26 O\x27Reilly\x21',
                    r'greeting\x3dH%69\x26addressee\x3d(World)',
                    ),
                ),
            (
                '<button onclick=\'alert("{{.}}")\'>',
                (
                    r'\x3cb\x3e \x22foo%\x22 O\x27Reilly \x26bar;',
                    r'a[href \x3d~ \x22\/\/example.com\x22]#foo',
                    r'Hello, \x3cb\x3eWorld\x3c\/b\x3e \x26amp;tc!',
                    r' dir\x3d\x22ltr\x22',
                    r'c \x26\x26 alert(\x22Hello, World!\x22);',
                    # Escape sequence not over-escaped.
                    r'Hello, World \x26 O\x27Reilly\x21',
                    r'greeting\x3dH%69\x26addressee\x3d(World)',
                    ),
                ),
            (
                '<a href="?q={{.}}">',
                (
                    '%3cb%3e%20%22foo%25%22%20O%27Reilly%20%26bar%3b',
                    'a%5bhref%20%3d~%20%22%2f%2fexample.com%22%5d%23foo',
                    'Hello%2c%20%3cb%3eWorld%3c%2fb%3e%20%26amp%3btc%21',
                    '%20dir%3d%22ltr%22',
                    'c%20%26%26%20alert%28%22Hello%2c%20World%21%22%29%3b',
                    'Hello%2c%20World%20%26%20O%27Reilly%5cx21',
                    # Quotes and parens are escaped but %69 is not over-escaped.
                    # HTML escaping is done.
                    'greeting=H%69&amp;addressee=%28World%29',
                    ),
                ),
            (
                "<style>body { background: url('?img={{.}}') }</style>",
                (
                    '%3cb%3e%20%22foo%25%22%20O%27Reilly%20%26bar%3b',
                    'a%5bhref%20%3d~%20%22%2f%2fexample.com%22%5d%23foo',
                    'Hello%2c%20%3cb%3eWorld%3c%2fb%3e%20%26amp%3btc%21',
                    '%20dir%3d%22ltr%22',
                    'c%20%26%26%20alert%28%22Hello%2c%20World%21%22%29%3b',
                    'Hello%2c%20World%20%26%20O%27Reilly%5cx21',
                    # Quotes and parens are escaped but %69 is not over-escaped.
                    # HTML escaping is not done.
                    'greeting=H%69&addressee=%28World%29',
                    ),
                ),
            )

        for tmpl_code, want_arr in tests:
            env = template.parse_templates('test', tmpl_code, 'main')
            escape.escape(env.templates, ('main',))
            pre = tmpl_code.find('{{.}}')
            post = len(tmpl_code) - (pre + 5)
            for i in xrange(0, len(data)):
                datum, want = data[i], want_arr[i]
                rendered = env.with_data(datum).sexecute('main')
                # got is just the portion of the template that does
                # not correspond to a literal text node in the input template.
                got = rendered[pre:len(rendered)-post]
                self.assertEquals(
                    want, got,
                    '%s with %r\n\t%r\n!=\n\t%r' % (
                        tmpl_code, datum, want, got))


if __name__ == '__main__':
    unittest.main()
