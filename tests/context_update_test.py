#!/usr/bin/python

"""Unit tests for context_update.py"""

import content
import context
import context_update
import debug
import escape
import escaping
import sys
import template
import unittest


class ContextUpdateTest(unittest.TestCase):
    """
    Tests the raw text update step defined in context_update and ancillary
    functions.
    """

    def test_escape_text(self):
        """
        Tests the content propagation algorithm.
        """
        tests = (
            (
                "",
                0,
            ),
            (
                'Hello, World!',
                0,
                ),
            (
                # An orphaned "<" is OK.
                'I <3 Ponies!',
                0,
                'I &lt;3 Ponies!',
                ),
            (
                '<a',
                context.STATE_TAG_NAME,
                ),
            (
                '<a ',
                context.STATE_TAG,
                ),
            (
                '<a>',
                context.STATE_TEXT,
                ),
            (
                '<a href',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a on',
                context.STATE_ATTR_NAME | context.ATTR_SCRIPT,
                ),
            (
                '<a href ',
                context.STATE_AFTER_NAME | context.ATTR_URL,
                ),
            (
                '<a style  =  ',
                context.STATE_BEFORE_VALUE | context.ATTR_STYLE,
                ),
            (
                '<a href=',
                context.STATE_BEFORE_VALUE | context.ATTR_URL,
                ),
            (
                '<a href=x',
                context.STATE_URL | context.DELIM_SPACE_OR_TAG_END
                | context.URL_PART_PRE_QUERY,
                '<a href="x',
                ),
            (
                '<a href=x ',
                context.STATE_TAG,
                '<a href="x" ',
                ),
            (
                '<a href=>',
                context.STATE_TEXT,
                '<a href="">',
                ),
            (
                '<a href=x>',
                context.STATE_TEXT,
                '<a href="x">',
                ),
            (
                "<a href ='",
                context.STATE_URL | context.DELIM_SINGLE_QUOTE,
                ),
            (
                "<a href=''",
                context.STATE_TAG,
                ),
            (
                '<a href= "',
                context.STATE_URL | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a href=""',
                context.STATE_TAG,
                ),
            (
                '<a title="',
                context.STATE_ATTR | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                "<a HREF='http:",
                context.STATE_URL | context.DELIM_SINGLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                "<a Href='/",
                context.STATE_URL | context.DELIM_SINGLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                "<a href='\"",
                context.STATE_URL | context.DELIM_SINGLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a href="\'',
                context.STATE_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                "<a href='&apos;",
                context.STATE_URL | context.DELIM_SINGLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                "<a href='&#39;",
                ),
            (
                '<a href="&quot;',
                context.STATE_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                '<a href="&#34;',
                ),
            (
                '<a href="&#34;',
                context.STATE_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a href=&quot;',
                context.STATE_URL | context.DELIM_SPACE_OR_TAG_END
                | context.URL_PART_PRE_QUERY,
                '<a href="&#34;',
                ),
            (
                '<a href="/search?q=',
                context.STATE_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_QUERY_OR_FRAG,
                ),
            (
                '<img alt="1">',
                context.STATE_TEXT,
                ),
            (
                '<img alt="1>"',
                context.STATE_TAG,
                '<img alt="1&gt;"',
                ),
            (
                '<img alt="1>">',
                context.STATE_TEXT,
                '<img alt="1&gt;">',
                ),
            (
                '<input checked type="checkbox"',
                context.STATE_TAG,
                ),
            (
                '<a onclick="',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="//foo',
                context.STATE_JSLINE_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a onclick="',
                ),
            (
                "<a onclick='//\n",
                context.STATE_JS | context.DELIM_SINGLE_QUOTE,
                "<a onclick='\n",
                ),
            (
                "<a onclick='//\r\n",
                context.STATE_JS | context.DELIM_SINGLE_QUOTE,
                "<a onclick='\n\n",  # \n\n is ok, \n is ok, \r\n is ok
                ),
            (
                u"<a onclick='//\u2028",
                context.STATE_JS | context.DELIM_SINGLE_QUOTE,
                "<a onclick='\n",
                ),
            (
                '<a onclick="/*',
                context.STATE_JSBLOCK_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a onclick=" ',
                ),
            (
                '<a onclick="/*/',
                context.STATE_JSBLOCK_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a onclick=" ',
                ),
            (
                '<a onclick="/**/',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE,
                '<a onclick=" ',
                ),
            (
                '<a onkeypress="&quot;',
                context.STATE_JSDQ_STR | context.DELIM_DOUBLE_QUOTE,
                '<a onkeypress="&#34;',
                ),
            (
                "<a onclick='&quot;foo&quot;",
                context.STATE_JS | context.DELIM_SINGLE_QUOTE
                | context.JS_CTX_DIV_OP,
                "<a onclick='\"foo\"",
                ),
            (
                '<a onclick=&#39;foo&#39;',
                context.STATE_JS | context.DELIM_SPACE_OR_TAG_END
                | context.JS_CTX_DIV_OP,
                '<a onclick="\'foo\'',
                ),
            (
                '<a onclick=&#39;foo',
                context.STATE_JSSQ_STR | context.DELIM_SPACE_OR_TAG_END,
                '<a onclick="\'foo',
                ),
            (
                '<a onclick="&quot;foo\'',
                context.STATE_JSDQ_STR | context.DELIM_DOUBLE_QUOTE,
                '<a onclick="&#34;foo\'',
                ),
            (
                '<a onclick="\'foo&quot;',
                context.STATE_JSSQ_STR | context.DELIM_DOUBLE_QUOTE,
                '<a onclick="\'foo&#34;',
                ),
            (
                '<A ONCLICK="\'',
                context.STATE_JSSQ_STR | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="/',
                context.STATE_JSREGEXP | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="\'foo\'',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE
                | context.JS_CTX_DIV_OP,
                ),
            (
                '<a onclick="\'foo\\\'',
                context.STATE_JSSQ_STR | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="\'foo\\\'',
                context.STATE_JSSQ_STR | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="/foo/',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE
                | context.JS_CTX_DIV_OP,
                ),
            (
                '<script>/foo/ /=',
                context.STATE_JS | context.ELEMENT_SCRIPT,
                ),
            (
                '<a onclick="1 /foo',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE
                | context.JS_CTX_DIV_OP,
                ),
            (
                '<a onclick="1 /*c*/ /foo',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE
                | context.JS_CTX_DIV_OP,
                '<a onclick="1   /foo',
                ),
            (
                '<a onclick="/foo[/]',
                context.STATE_JSREGEXP | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="/foo\\/',
                context.STATE_JSREGEXP | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a onclick="/foo/',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE
                | context.JS_CTX_DIV_OP,
                ),
            (
                '<input checked style="',
                context.STATE_CSS | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a style="//',
                context.STATE_CSSLINE_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a style="',
                ),
            (
                '<a style="//</script>',
                context.STATE_CSSLINE_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a style="',
                ),
            (
                "<a style='//\n",
                context.STATE_CSS | context.DELIM_SINGLE_QUOTE,
                "<a style='\n",
                ),
            (
                "<a style='//\r",
                context.STATE_CSS | context.DELIM_SINGLE_QUOTE,
                "<a style='\n",
                ),
            (
                '<a style="/*',
                context.STATE_CSSBLOCK_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a style=" ',
                ),
            (
                '<a style="/*/',
                context.STATE_CSSBLOCK_CMT | context.DELIM_DOUBLE_QUOTE,
                '<a style=" ',
                ),
            (
                '<a style="/**/',
                context.STATE_CSS | context.DELIM_DOUBLE_QUOTE,
                '<a style=" ',
                ),
            (
                '<a style="background: \'',
                context.STATE_CSSSQ_STR | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a style="background: &quot;',
                context.STATE_CSSDQ_STR | context.DELIM_DOUBLE_QUOTE,
                '<a style="background: &#34;',
                ),
            (
                '<a style="background: \'/foo?img=',
                context.STATE_CSSSQ_STR | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_QUERY_OR_FRAG,
                ),
            (
                '<a style="background: \'/',
                context.STATE_CSSSQ_STR | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a style="background: url(&#x22;/',
                context.STATE_CSSDQ_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                '<a style="background: url(&#34;/',
                ),
            (
                '<a style="background: url(\'/',
                context.STATE_CSSSQ_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a style="background: url(\'/)',
                context.STATE_CSSSQ_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a style="background: url(\'/ ',
                context.STATE_CSSSQ_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a style="background: url(/',
                context.STATE_CSS_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_PRE_QUERY,
                ),
            (
                '<a style="background: url( ',
                context.STATE_CSS_URL | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a style="background: url( /image?name=',
                context.STATE_CSS_URL | context.DELIM_DOUBLE_QUOTE
                | context.URL_PART_QUERY_OR_FRAG,
                ),
            (
                '<a style="background: url(x)',
                context.STATE_CSS | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a style="background: url(\'x\'',
                context.STATE_CSS | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<a style="background: url( x ',
                context.STATE_CSS | context.DELIM_DOUBLE_QUOTE,
                ),
            (
                '<!-- foo',
                context.STATE_HTMLCMT,
                '',
                ),
            (
                '<!-->',
                context.STATE_HTMLCMT,
                '',
                ),
            (
                '<!--->',
                context.STATE_HTMLCMT,
                '',
                ),
            (
                '<!-- foo -->',
                context.STATE_TEXT,
                '',
                ),
            (
                '<script',
                context.STATE_TAG | context.ELEMENT_SCRIPT,
                ),
            (
                '<script ',
                context.STATE_TAG | context.ELEMENT_SCRIPT,
                ),
            (
                '<script src="foo.js" ',
                context.STATE_TAG | context.ELEMENT_SCRIPT,
                ),
            (
                "<script src='foo.js' ",
                context.STATE_TAG | context.ELEMENT_SCRIPT,
                ),
            (
                '<script type=text/javascript ',
                context.STATE_TAG | context.ELEMENT_SCRIPT,
                '<script type="text/javascript" ',
                ),
            (
                '<script>foo',
                context.STATE_JS | context.JS_CTX_DIV_OP
                | context.ELEMENT_SCRIPT,
                ),
            (
                '<script>foo</script>',
                context.STATE_TEXT,
                ),
            (
                '<script>foo</script><!--',
                context.STATE_HTMLCMT,
                '<script>foo</script>',
                ),
            (
                '<script>document.write("<p>foo</p>");',
                context.STATE_JS | context.ELEMENT_SCRIPT,
                ),
            (
                r'<script>document.write("<p>foo<\/script>");',
                context.STATE_JS | context.ELEMENT_SCRIPT,
                ),
            (
                '<script>document.write("<script>alert(1)</script>");',
                context.STATE_TEXT,
                ),
            (
                '<Script>',
                context.STATE_JS | context.ELEMENT_SCRIPT,
                ),
            (
                '<SCRIPT>foo',
                context.STATE_JS | context.JS_CTX_DIV_OP
                | context.ELEMENT_SCRIPT,
                ),
            (
                '<textarea>value',
                context.STATE_RCDATA | context.ELEMENT_TEXTAREA,
                ),
            (
                '<textarea>value</textarea>',
                context.STATE_TEXT,
                ),
            (
                '<textarea>value</TEXTAREA>',
                context.STATE_TEXT,
                ),
            (
                '<textarea name=html><b',
                context.STATE_RCDATA | context.ELEMENT_TEXTAREA,
                '<textarea name="html">&lt;b',
                ),
            (
                '<title>value',
                context.STATE_RCDATA | context.ELEMENT_TITLE,
                ),
            (
                '<style>value',
                context.STATE_CSS | context.ELEMENT_STYLE,
                ),
            (
                '<a xlink:href',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a xmlns',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a xmlns:foo',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a xmlnsxyz',
                context.STATE_ATTR_NAME,
                ),
            (
                '<a data-url',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a data-iconUri',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a data-urlItem',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a g:',
                context.STATE_ATTR_NAME,
                ),
            (
                '<a g:url',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a g:iconUri',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a g:urlItem',
                context.STATE_ATTR_NAME | context.ATTR_URL,
                ),
            (
                '<a g:value',
                context.STATE_ATTR_NAME,
                ),
            (
                "<a svg:style='",
                context.STATE_CSS | context.DELIM_SINGLE_QUOTE,
                ),
            (
                '<svg:font-face',
                context.STATE_TAG_NAME,
                ),
            (
                '<svg:a svg:onclick="',
                context.STATE_JS | context.DELIM_DOUBLE_QUOTE,
                )
            )

        for test_case in tests:
            if len(test_case) == 2:
                test_input, want_ctx = test_case
                want_text = test_input
            else:
                test_input, want_ctx, want_text = test_case
            got_ctx, got_text, _, _ = context_update.process_raw_text(
                test_input, 0)
            if got_ctx != want_ctx:
                self.fail("input %r: want context\n\t%s\ngot\n\t%s"
                          % (test_input, debug.context_to_string(want_ctx),
                             debug.context_to_string(got_ctx)))
            self.assertEquals(
                got_text, want_text,
                msg = ("input %r: want text\n\t%r\ngot\n\t%r"
                       % (test_input, want_text, got_text)))


    def test_redundant_funcs(self):
        """
        Check that the redundant funcs invariant holds.
        """
        inputs = (
            ("\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f"
             "\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
             " !\"#$%&'()*+,-./"
             "0123456789:;<=>?"
             "@ABCDEFGHIJKLMNO"
             "PQRSTUVWXYZ[\]^_"
             "`abcdefghijklmno"
             "pqrstuvwxyz{|}~\x7f"
             "\u00A0\u0100\u2028\u2029\ufeff\ufdec\ufffd\uffff\U0001D11E"
             "&amp;%22\\"),
            content.SafeCSS('a[href =~ "//example.com"]#foo'),
            content.SafeHTML('Hello, <b>World</b> &amp;tc!'),
            content.SafeHTMLAttr(' dir="ltr"'),
            content.SafeJS('c && alert("Hello, World!");'),
            content.SafeJSStr(r"Hello, World & O'Reilly\x21"),
            content.SafeURL('greeting=H%69&addressee=(World)'),
            )

        for fi0, fi1 in escaping.REDUNDANT_ESC_MODES:
            fn0 = escaping.SANITIZER_FOR_ESC_MODE[fi0]
            fn1 = escaping.SANITIZER_FOR_ESC_MODE[fi1]
            for test_input in inputs:
                want = fn0(test_input)
                got = fn1(want)
                if want != got:
                    self.fail(
                        "%s %s with %r: want\n\t%r,\ngot\n\t%r"
                        % (fn0.__name__, fn1.__name__, test_input, want, got))



if __name__ == '__main__':
    if len(sys.argv) == 2 and '-' == sys.argv[1]:
        def _tmpls_from_stdin():
            """Read template from stdin and dump the output to stdout."""
            code = sys.stdin.read().decode('UTF-8')
            env = template.parse_templates('-', code, 'main')
            escape.escape(env.templates, ('main',))
            print env.sexecute('main')
        _tmpls_from_stdin()
    else:
        unittest.main()
