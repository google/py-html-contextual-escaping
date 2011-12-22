#!/usr/bin/python

"""Unit tests for context_update.py"""

import content
import context
import context_update
import debug
import escape
import sys
import template
import unittest

class WidgyMarshaler(object):
    """A JSON Marshaller that contains widgy data"""
    def to_json(self):
        """Satisfies the interface expected by escape_js_value."""
        return { "foo": u"\u2028--></script>" }


class BadMarshaler(object):
    """A JSON Marshaller that fails to marshal"""
    def to_json(self):
        """Satisfies the interface expected by escape_js_value."""
        raise RuntimeError("Cannot marshal")


class GoodMarshaler(object):
    """A JSON Marshaller containing innocuous data."""
    def to_json(self):
        """Satisfies the interface expected by escape_js_value."""
        return { "foo": "bar", "baz": ["boo", 42, "far", None, float("nan")] }


class ContextUpdateTest(unittest.TestCase):
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
            if got_text != want_text:
                self.fail("input %r: want text\n\t%r\ngot\n\t%r"
                          % (test_input, want_text, got_text)),

    def test_escape(self):
        """
        Tests the result of running escaped templates.
        """
        data = {
            "F": False,
            "T": True,
            "C": "<Cincinatti>",
            "G": "<Goodbye>",
            "H": "<Hello>",
            "A": ("<a>", "<b>"),
            "E": (),
            "N": 42,
            "B": BadMarshaler(),
            "M": GoodMarshaler(),
            "Q": WidgyMarshaler(),
            "Z": None,
            "W": content.SafeHTML(
                '&iexcl;<b class="foo">Hello</b>,'
                ' <textarea>O\'World</textarea>!'),
            }

        tests = ((
            "if",
            "{{if .T}}Hello{{end}}, {{.C}}!",
            "Hello, &lt;Cincinatti&gt;!",
        ),
        (
            "else",
            "{{if .F}}{{.H}}{{else}}{{.G}}{{end}}!",
            "&lt;Goodbye&gt;!",
        ),
        (
            "overescaping1",
            "Hello, {{.C | escape_html}}!",
            "Hello, &lt;Cincinatti&gt;!",
        ),
        (
            "overescaping2",
            "Hello, {{escape_html(.C)}}!",
            "Hello, &lt;Cincinatti&gt;!",
        ),
        (
            "withBody",
            "{{with .H}}{{.}}{{end}}",
            "&lt;Hello&gt;",
        ),
        (
            "withElse",
            "{{with .E}}{{.}}{{else}}{{.H}}{{end}}",
            "&lt;Hello&gt;",
        ),
        (
            "rangeBody",
            "{{range .A}}{{.}}{{end}}",
            "&lt;a&gt;&lt;b&gt;",
        ),
        (
            "rangeElse",
            "{{range .E}}{{.}}{{else}}{{.H}}{{end}}",
            "&lt;Hello&gt;",
        ),
        (
            "nonStringValue",
            "{{.T}}",
            "True",
        ),
        (
            "constant",
            "<a href=\"/search?q={{\"'a<b'\"}}\">",
            '<a href="/search?q=%27a%3cb%27">',
        ),
        (
            "multipleAttrs",
            "<a b=1 c={{.H}}>",
            '<a b="1" c="&lt;Hello&gt;">',
        ),
        (
            "urlStartRel",
            r"""<a href='{{"/foo/bar?a=b&c=d"}}'>""",
            "<a href='/foo/bar?a=b&amp;c=d'>",
        ),
        (
            "urlStartAbsOk",
            r"""<a href='{{"http://example.com/foo/bar?a=b&c=d"}}'>""",
            "<a href='http://example.com/foo/bar?a=b&amp;c=d'>",
        ),
        (
            "protocolRelativeURLStart",
            r"""<a href='{{"//example.com:8000/foo/bar?a=b&c=d"}}'>""",
            "<a href='//example.com:8000/foo/bar?a=b&amp;c=d'>",
        ),
        (
            "pathRelativeURLStart",
            '<a href="{{"/javascript:80/foo/bar"}}">',
            '<a href="/javascript:80/foo/bar">',
        ),
        (
            "dangerousURLStart",
            r"""<a href='{{"javascript:alert(%22pwned%22)"}}'>""",
            "<a href='#zSafehtmlz'>",
        ),
        (
            "dangerousURLStart2",
            r"""<a href='  {{"javascript:alert(%22pwned%22)"}}'>""",
            "<a href='  #zSafehtmlz'>",
        ),
        (
            "nonHierURL",
            ('<a href={{"mailto:Muhammed \\"The Greatest\\" Ali'
             ' <m.ali@example.com>"}}>'),
            ('<a href="mailto:Muhammed%20%22The%20Greatest%22%20Ali'
             '%20%3cm.ali@example.com%3e">'),
        ),
        (
            "urlPath",
            r"""<a href='http://{{"javascript:80"}}/foo'>""",
            "<a href='http://javascript:80/foo'>",
        ),
        (
            "urlQuery",
            "<a href='/search?q={{.H}}'>",
            "<a href='/search?q=%3cHello%3e'>",
        ),
        (
            "urlFragment",
            "<a href='/faq#{{.H}}'>",
            "<a href='/faq#%3cHello%3e'>",
        ),
        (
            "urlBranch",
            '<a href="{{if .F}}/foo?a=b{{else}}/bar{{end}}">',
            '<a href="/bar">',
        ),
        (
            "urlBranchConflictMoot",
            '<a href="{{if .T}}/foo?a={{else}}/bar#{{end}}{{.C}}">',
            '<a href="/foo?a=%3cCincinatti%3e">',
        ),
        (
            "jsStrValue",
            "<button onclick='alert({{.H}})'>",
            r"<button onclick='alert(&#34;\x3cHello\x3e&#34;)'>",
        ),
        (
            "jsNumericValue",
            "<button onclick='alert({{.N}})'>",
            "<button onclick='alert( 42 )'>",
        ),
        (
            "jsBoolValue",
            "<button onclick='alert({{.T}})'>",
            "<button onclick='alert( true )'>",
        ),
        (
            "jsNilValue",
            "<button onclick='alert(typeof{{.Z}})'>",
            "<button onclick='alert(typeof null )'>",
        ),
        (
            "jsObjValue",
            "<button onclick='alert({{.A}})'>",
            (r"<button onclick='alert("
             r"[&#34;\x3ca\x3e&#34;,&#34;\x3cb\x3e&#34;])'>"),
        ),
        (
            "jsObjValueScript",
            "<script>alert({{.A}})</script>",
            r'<script>alert(["\x3ca\x3e","\x3cb\x3e"])</script>',
        ),
        (
            "jsObjValueNotOverEscaped",
            "<button onclick='alert({{.A | escape_html}})'>",
            (r"<button onclick='alert("
             r"[&#34;\x3ca\x3e&#34;,&#34;\x3cb\x3e&#34;])'>"),
        ),
        (
            "jsStr",
            "<button onclick='alert(&quot;{{.H}}&quot;)'>",
            "<button onclick='alert(\"\\x3cHello\\x3e\")'>",
        ),
        (
            "badMarshaller",
            "<button onclick='alert(1/{{.B}}in numbers)'>",
            ("<button onclick='alert(1/ null in numbers)'>"),
        ),
        (
            "widgyMarshaller",
            "<button onclick='alert(1/{{.Q}}in numbers)'>",
            (r"<button onclick='alert(1/"
             r"({&#34;foo&#34;:&#34;\u2028--\x3e\x3c/script\x3e&#34;})"
             r"in numbers)'>"),
        ),
        (
            "jsMarshaller",
            "<button onclick='alert({{.M}})'>",
            ("<button onclick='alert("
             "({&#34;foo&#34;:&#34;bar&#34;,"
             "&#34;baz&#34;:[&#34;boo&#34;,42,&#34;far&#34;,null,NaN]})"
             ")'>"),
        ),
        (
            "jsStrNotUnderEscaped",
            "<button onclick='alert({{.C | escape_url}})'>",
            # URL escaped, then quoted for JS.
            "<button onclick='alert(&#34;%3cCincinatti%3e&#34;)'>",
        ),
        (
            "jsRe",
            r"""<button onclick='alert(/{{"foo+bar"}}/.test(""))'>""",
            r"""<button onclick='alert(/foo\x2bbar/.test(""))'>""",
        ),
        (
            "jsReBlank",
            '<script>alert(/{{""}}/.test(""));</script>',
            '<script>alert(/(?:)/.test(""));</script>',
        ),
        (
            "jsReAmbigOk",
            '<script>{{if True}}var x = 1{{end}}</script>',
            # The {if} ends in an ambiguous jsCtx but there is
            # no slash following so we shouldn't care.
            '<script>var x = 1</script>',
        ),
        (
            "styleBidiKeywordPassed",
            '<p style="dir: {{"ltr"}}">',
            '<p style="dir: ltr">',
        ),
        (
            "styleBidiPropNamePassed",
            '<p style="border-{{"left"}}: 0; border-{{"right"}}: 1in">',
            '<p style="border-left: 0; border-right: 1in">',
        ),
        (
            "styleExpressionBlocked",
            '<p style="width: {{"expression(alert(1337))"}}">',
            '<p style="width: zSafehtmlz">',
        ),
        (
            "styleTagSelectorPassed",
            '<style>{{"p"}} { color: pink }</style>',
            '<style>p { color: pink }</style>',
        ),
        (
            "styleIDPassed",
            '<style>p{{"#my-ID"}} { font: Arial }</style>',
            '<style>p#my-ID { font: Arial }</style>',
        ),
        (
            "styleClassPassed",
            '<style>p{{".my_class"}} { font: Arial }</style>',
            '<style>p.my_class { font: Arial }</style>',
        ),
        (
            "styleQuantityPassed",
            '<a style="left: {{"2em"}}; top: {{0}}">',
            '<a style="left: 2em; top: 0">',
        ),
        (
            "stylePctPassed",
            '<table style=width:{{"100%"}}>',
            '<table style="width:100%">',
        ),
        (
            "styleColorPassed",
            '<p style="color: {{"#8ff"}}; background: {{"#000"}}">',
            '<p style="color: #8ff; background: #000">',
        ),
        (
            "styleObfuscatedExpressionBlocked",
            r'<p style="width: {{"  e\78preS\0Sio/**/n(alert(1337))"}}">',
            '<p style="width: zSafehtmlz">',
        ),
        (
            "styleMozBindingBlocked",
            '<p style="{{"-moz-binding(alert(1337))"}}: ...">',
            '<p style="zSafehtmlz: ...">',
        ),
        (
            "styleObfuscatedMozBindingBlocked",
            r'<p style="{{"  -mo\7a-B\0I/**/nding(alert(1337))"}}: ...">',
            '<p style="zSafehtmlz: ...">',
        ),
        (
            "styleFontNameString",
            r"""<p style='font-family: "{{"Times New Roman"}}"'>""",
            r"""<p style='font-family: "Times New Roman"'>""",
        ),
        (
            "styleFontNameString",
            ('<p style=\'font-family:'
             ' "{{"Times New Roman"}}", "{{"sans-serif"}}"\'>'),
            '<p style=\'font-family: "Times New Roman", "sans-serif"\'>',
        ),
        (
            "styleFontNameUnquoted",
            r"""<p style='font-family: {{"Times New Roman"}}'>""",
            "<p style='font-family: Times New Roman'>",
        ),
        (
            "styleURLQueryEncoded",
            ('<p style="background:'
             ' url(/img?name={{"O\'Reilly Animal(1)<2>.png"}})">'),
            ('<p style="background:'
             ' url(/img?name=O%27Reilly%20Animal%281%29%3c2%3e.png)">'),
        ),
        (
            "styleQuotedURLQueryEncoded",
            ("<p style=\"background:"
             " url('/img?name={{\"O'Reilly Animal(1)<2>.png\"}}')\">"),
            ("<p style=\"background:"
             " url('/img?name=O%27Reilly%20Animal%281%29%3c2%3e.png')\">"),
        ),
        (
            "styleStrQueryEncoded",
            ("<p style=\"background: "
             "'/img?name={{\"O'Reilly Animal(1)<2>.png\"}}'\">"),
            ("<p style=\"background: "
             "'/img?name=O%27Reilly%20Animal%281%29%3c2%3e.png'\">"),
        ),
        (
            "styleURLBadProtocolBlocked",
            r"""<a style="background: url('{{"javascript:alert(1337)"}}')">""",
            r"""<a style="background: url('#zSafehtmlz')">""",
        ),
        (
            "styleStrBadProtocolBlocked",
            r"""<a style="background: '{{"vbscript:alert(1337)"}}'">""",
            r"""<a style="background: '#zSafehtmlz'">""",
        ),
        (
            "styleStrEncodedProtocolEncoded",
            r"""<a style="background:'{{"javascript\\3a alert(1337)"}}'">""",
            # The CSS string 'javascript\\3a alert(1337)' does not contain
            # a colon.
            r"""<a style="background:'javascript\\3a alert\28 1337\29 '">""",
        ),
        (
            "styleURLGoodProtocolPassed",
            ("<a style=\"background: url("
             "'{{\"http://oreilly.com/O'Reilly Animals(1)<2>;{}.html\"}}')\">"),
            ("<a style=\"background: url("
             "'http://oreilly.com/"
             "O%27Reilly%20Animals%281%29%3c2%3e;%7b%7d.html')\">"),
        ),
        (
            "styleStrGoodProtocolPassed",
            ("<a style=\"background:"
             " '{{\"http://oreilly.com/O'Reilly Animals(1)<2>;{}.html\"}}'\">"),
            (r'<a style="background:'
             r" 'http\3a \2f \2f oreilly.com\2f "
             r"O\27 Reilly Animals\28 1\29 \3c 2\3e "
             r"\3b \7b \7d .html'"
             r'">'),
        ),
        (
            "styleURLEncodedForHTMLInAttr",
            '<a style=\"background: url(\'{{"/search?img=foo&size=icon"}}\')">',
            '<a style="background: url(\'/search?img=foo&amp;size=icon\')">',
        ),
        (
            "styleURLNotEncodedForHTMLInCdata",
            ('<style>body { background:'
             ' url(\'{{"/search?img=foo&size=icon"}}\') }</style>'),
            ('<style>body { background:'
             ' url(\'/search?img=foo&size=icon\') }</style>'),
        ),
        (
            "styleURLMixedCase",
            '<p style="background: URL(#{{.H}})">',
            '<p style="background: URL(#%3cHello%3e)">',
        ),
        (
            "stylePropertyPairPassed",
            "<a style='{{\"color: red\"}}'>",
            "<a style='color: red'>",
        ),
        (
            "styleStrSpecialsEncoded",
            ("<a style=\"font-family:"
             " '{{\"/**/'\\\";:// \\\\\"}}',"
             " &quot;{{\"/**/'\\\";:// \\\\\"}}&quot;\">"),
            (r'<a style="font-family:'
             r" '\2f \2a \2a \2f \27 \22 \3b \3a \2f \2f  \\',"
             r' &#34;\2f \2a \2a \2f \27 \22 \3b \3a \2f \2f  \\&#34;">'),
        ),
        (
            "styleURLSpecialsEncoded",
            ('<a style="border-image:'
             ' url({{"/**/\'\\";:// \\\\"}}),'
             ' url(&quot;{{"/**/\'\\";:// \\\\"}}&quot;),'
             ' url(\'{{"/**/\'\\";:// \\\\"}}\'),'
             ' \'http://www.example.com/?q={{"/**/\'\\";:// \\\\"}}\''
             '">'),
            ('<a style="border-image:'
             ' url(/**/%27%22;://%20%5c),'
             ' url(&#34;/**/%27%22;://%20%5c&#34;),'
             " url('/**/%27%22;://%20%5c'),"
             " 'http://www.example.com/?q=%2f%2a%2a%2f%27%22%3b%3a%2f%2f%20%5c'"
             '">'),
        ),
        (
            "HTML comment",
            "<b>Hello, <!-- name of world -->{{.C}}</b>",
            "<b>Hello, &lt;Cincinatti&gt;</b>",
        ),
        (
            "HTML comment not first < in text node.",
            "<<!-- -->!--",
            "&lt;!--",
        ),
        (
            "HTML normalization 1",
            "a < b",
            "a &lt; b",
        ),
        (
            "HTML normalization 2",
            "a << b",
            "a &lt;&lt; b",
        ),
        (
            "HTML normalization 3",
            "a<<!-- --><!-- -->b",
            "a&lt;b",
        ),
        (
            "HTML doctype not normalized",
            "<!DOCTYPE html>Hello, World!",
            "<!DOCTYPE html>Hello, World!",
        ),
        (
            "No doctype injection",
            '<!{{"DOCTYPE"}}',
            "&lt;!DOCTYPE",
        ),
        (
            "Split HTML comment",
            ("<b>Hello, <!-- name of {{if .T}}city -->{{.C}}{{else}}world -->"
             "{{.W}}{{end}}</b>"),
            "<b>Hello, &lt;Cincinatti&gt;</b>",
        ),
        (
            "JS line comment",
            "<script>for (;;) { if (c()) break// foo not a label\n" +
                "foo({{.T}});}</script>",
            "<script>for (;;) { if (c()) break\n" +
                "foo( true );}</script>",
        ),
        (
            "JS multiline block comment",
            "<script>for (;;) { if (c()) break/* foo not a label\n" +
                " */foo({{.T}});}</script>",
            # Newline separates break from call. If newline
            # removed, then break will consume label leaving
            # code invalid.
            "<script>for (;;) { if (c()) break \n" +
                "foo( true );}</script>",
        ),
        (
            "JS single-line block comment",
            "<script>for (;;) {\n" +
                "if (c()) break/* foo a label */foo;" +
                "x({{.T}});}</script>",
            # Newline separates break from call. If newline
            # removed, then break will consume label leaving
            # code invalid.
            "<script>for (;;) {\n" +
                "if (c()) break foo;" +
                "x( true );}</script>",
        ),
        (
            "JS block comment flush with mathematical division",
            "<script>var a/*b*//c\nd</script>",
            "<script>var a /c\nd</script>",
        ),
        (
            "JS mixed comments",
            "<script>var a/*b*///c\nd</script>",
            "<script>var a \nd</script>",
        ),
        (
            "CSS comments",
            "<style>p// paragraph\n" +
                '{border: 1px/* color */{{"#00f"}}}</style>',
            "<style>p\n" +
                "{border: 1px #00f}</style>",
        ),
        (
            "JS attr block comment",
            '<a onclick="f(&quot;&quot;); /* alert({{.H}}) */">',
            # Attribute comment tests should pass if the comments
            # are successfully elided.
            '<a onclick="f(&#34;&#34;);  ">',
        ),
        (
            "JS attr line comment",
            '<a onclick="// alert({{.G}})">',
            '<a onclick="">',
        ),
        (
            "CSS attr block comment",
            '<a style="/* color: {{.H}} */">',
            '<a style=" ">',
        ),
        (
            "CSS attr line comment",
            '<a style="// color: {{.G}}">',
            '<a style="">',
        ),
        (
            "HTML substitution commented out",
            "<p><!-- {{.H}} --></p>",
            "<p></p>",
        ),
        (
            "Comment ends flush with start",
            ("<!--{{.}}--><script>/*{{.}}*///{{.}}\n</script>"
             "<style>/*{{.}}*///{{.}}\n</style>"
             "<a onclick='/*{{.}}*///{{.}}' style='/*{{.}}*///{{.}}'>"),
            ("<script> \n</script>"
             "<style> \n</style>"
             "<a onclick=' ' style=' '>"),
        ),
        (
            "typed HTML in text",
            '{{.W}}',
            '&iexcl;<b class="foo">Hello</b>, <textarea>O\'World</textarea>!',
        ),
        (
            "typed HTML in attribute",
            '<div title="{{.W}}">',
            '<div title="&iexcl;Hello, O&#39;World!">',
        ),
        (
            "typed HTML in script",
            '<button onclick="alert({{.W}})">',
            (r'<button onclick="alert('
             r'&#34;&amp;iexcl;\x3cb class=\&#34;foo\&#34;\x3e'
             r'Hello\x3c/b\x3e, '
             r'\x3ctextarea\x3eO&#39;World\x3c/textarea\x3e!&#34;)">'),
        ),
        (
            "typed HTML in RCDATA",
            '<textarea>{{.W}}</textarea>',
            ('<textarea>&iexcl;&lt;b class=&#34;foo&#34;&gt;Hello&lt;/b&gt;,'
             ' &lt;textarea&gt;O&#39;World&lt;/textarea&gt;!</textarea>'),
        ),
        (
            "range in textarea",
            "<textarea>{{range .A}}{{.}}{{end}}</textarea>",
            "<textarea>&lt;a&gt;&lt;b&gt;</textarea>",
        ),
        (
            "auditable exemption from escaping",
            "{{range .A}}{{. | noescape}}{{end}}",
            "<a><b>",
        ),
        (
            "No tag injection",
            '{{"10$"}}<{{"script src,evil.org/pwnd.js"}}...',
            '10$&lt;script src,evil.org/pwnd.js...',
        ),
        (
            "No comment injection",
            '<{{"!--"}}',
            '&lt;!--',
        ),
        (
            "No RCDATA end tag injection",
            '<textarea><{{"/textarea "}}...</textarea>',
            '<textarea>&lt;/textarea ...</textarea>',
        ),
        (
            "optional attrs",
            ("<img class=\"{{\"iconClass\"}}\"" +
                r"""{{if .T}} id="{{"<iconId>"}}"{{end}}""" +
                # Double quotes inside if/else.
                r""" src=""" +
                r'''{{if .T}}"?{{"<iconPath>"}}"''' +
                r"""{{else}}"images/cleardot.gif"{{end}}""" +
                # Missing space before title, but it is not a
                # part of the src attribute.
                r"""{{if .T}}title="{{"<title>"}}"{{end}}""" +
                # Quotes outside if/else.
                r''' alt="''' +
                r"""{{if .T}}{{"<alt>"}}""" +
                r"""{{else}}{{if .F}}{{"<title>"}}{{end}}""" +
                r'''{{end}}"''' +
                '>'),
            ('<img class="iconClass" id="&lt;iconId&gt;"'
             ' src="?%3ciconPath%3e"title="&lt;title&gt;" alt="&lt;alt&gt;">'),
        ),
        (
            "conditional valueless attr name",
            '<input{{if .T}} checked{{end}} name=n>',
            '<input checked name="n">',
        ),
        (
            "conditional dynamic valueless attr name 1",
            '<input{{if .T}} {{"checked"}}{{end}} name=n>',
            '<input checked name="n">',
        ),
        (
            "conditional dynamic valueless attr name 2",
            '<input {{if .T}}{{"checked"}} {{end}}name=n>',
            '<input checked name="n">',
        ),
        (
            "dynamic attribute name",
            '<img on{{"load"}}="alert({{"loaded"}})">',
            # Treated as JS since quotes are inserted.
            '<img onload="alert(&#34;loaded&#34;)">',
        ),
        (
            "bad dynamic attribute name 1",
            # Allow checked, selected, disabled, but not JS or
            # CSS attributes.
            '<input {{"onchange"}}="{{"doEvil()"}}">',
            '<input zSafehtmlz="doEvil()">',
        ),
        (
            "bad dynamic attribute name 2",
            '<div {{"sTyle"}}="{{"color: expression(alert(1337))"}}">',
            '<div zSafehtmlz="color: expression(alert(1337))">',
        ),
        (
            "bad dynamic attribute name 3",
            # Allow title or alt, but not a URL.
            '<img {{"src"}}="{{"javascript:doEvil()"}}">',
            '<img zSafehtmlz="javascript:doEvil()">',
        ),
        (
            "bad dynamic attribute name 4",
            # Structure preservation requires values to associate
            # with a consistent attribute.
            '<input checked {{""}}="Whose value am I?">',
            '<input checked zSafehtmlz="Whose value am I?">',
        ),
        (
            "dynamic element name",
            '<h{{3}}><table><t{{"head"}}>...</h{{3}}>',
            '<h3><table><thead>...</h3>',
        ),
        (
            "bad dynamic element name",
            # Dynamic element names are typically used to switch
            # between (thead, tfoot, tbody), (ul, ol), (th, td),
            # and other replaceable sets.
            # We do not currently easily support (ul, ol).
            # If we do change to support that, this test should
            # catch failures to filter out special tag names which
            # would violate the structure preservation property --
            # if any special tag name could be substituted, then
            # the content could be raw text/RCDATA for some inputs
            # and regular HTML content for others.
            '<{{"script"}}>{{"doEvil()"}}</{{"script"}}>',
            '&lt;script>doEvil()&lt;/script>',
        ),
        )

        report_all = False

        failures = []

        for name, test_input, want in tests:
            env = None
            try:
                env = template.parse_templates('test', test_input, 'main')
                escape.escape(env.templates, ('main',))
                got = env.with_data(data).sexecute('main')
            except:
                print >> sys.stderr, '\ntest_escape %s:\n%s\n' % (
                    name, test_input)
                if env is not None:
                    print >> sys.stderr, str(env)
                raise
            if want != got:
                msg = ("%s: escaped output: want\n\t%r\ngot\n\t%r"
                    % (name, want, got))
                if report_all:
                    failures.append(msg)
                else:
                    msg = '%s\n\tenv=%s' % (msg, env)
                    self.fail(msg)
        if failures:
            self.fail('\n\n'.join(failures))


    def test_escape_set(self):
        data = {
            "Children": [
                {"X": "foo"},
                {"X": "<bar>"},
                {
                    "Children": [
                        {"X": "baz"},
                        ],
                    },
                ],
            }

        tests = (
        # The trivial set.
        (
            {
                "main": "",
            },
            '',
        ),
        # A template called in the start context.
        (
            {
                "main": 'Hello, {{template "helper"}}!',
                # Not a valid top level HTML template.
                # "<b" is not a full tag.
                "helper": '{{"<World>"}}',
            },
            'Hello, &lt;World&gt;!',
        ),
        # A template called in a context other than the start.
        (
            {
                "main": "<a onclick='a = {{template \"helper\"}};'>",
                # Not a valid top level HTML template.
                # "<b" is not a full tag.
                "helper": '{{"<a>"}}<b',
            },
            r"<a onclick='a = &#34;\x3ca\x3e&#34;&lt;b;'>",
        ),
        # A recursive template that ends in its start context.
        (
            {
                "main": ('{{range .Children}}{{template "main" .}}'
                         '{{else}}{{.X}} {{end}}'),
            },
            'foo &lt;bar&gt; baz ',
        ),
        # A recursive helper template that ends in its start context.
        (
            {
                "main":   '{{template "helper" .}}',
                "helper": ('{{if .Children}}<ul>{{range .Children}}'
                           '<li>{{template "main" .}}</li>'
                           '{{end}}</ul>{{else}}{{.X}}{{end}}'),
            },
            ('<ul>'
             '<li>foo</li>'
             '<li>&lt;bar&gt;</li>'
             '<li><ul><li>baz</li></ul></li>'
             '</ul>'),
        ),
        # Co-recursive templates that end in its start context.
        (
            {
                "main":   ('<blockquote>'
                           '{{range .Children}}{{template "helper" .}}{{end}}'
                           '</blockquote>'),
                "helper": ('{{if .Children}}{{template "main" .}}'
                           '{{else}}{{.X}}<br>{{end}}'),
            },
            ('<blockquote>foo<br>&lt;bar&gt;<br>'
             '<blockquote>baz<br>'
             '</blockquote></blockquote>'),
        ),
        # A template that is called in two different contexts.
        (
            {
                "main":   ("<button onclick=\"title='"
                           "{{template \"helper\"}}'; ...\">"
                           "{{template \"helper\"}}</button>"),
                "helper": '{{11}} of {{"<100>"}}',
            },
            (r'<button onclick="'
             r"title='11 of \x3c100\x3e';"
             r' ...">11 of &lt;100&gt;</button>'),
        ),
        # A non-recursive template that ends in a different context.
        # helper starts in jsCtxRegexp and ends in jsCtxDivOp.
        (
            {
                "main":   ('<script>'
                           'var x={{template "helper"}}/{{"42"}};'
                           '</script>'),
                "helper": "{{126}}",
            },
            '<script>var x= 126 /"42";</script>',
        ),
        # A recursive template that ends in a similar context.
        (
            {
                "main":      ('<script>'
                              'var x=[{{template "countdown" 4}}];'
                              '</script>'),
                "countdown": ('{{.}}'
                              '{{if .}},{{template "countdown" . | pred}}'
                              '{{end}}'),
            },
            '<script>var x=[ 4 , 3 , 2 , 1 , 0 ];</script>',
        ),
        # A recursive template that ends in a different context.
        #
        #    (
        #        {
        #            "main":   '<a href="/foo{{template "helper" .}}">',
        #            "helper": ('{{if .Children}}'
        #                       '{{range .Children}}{{template "helper" .}}'
        #                       '{{end}}{{else}}?x={{.X}}{{end}}'),
        #        },
        #        '<a href="/foo?x=foo?x=%3cbar%3e?x=baz">',
        #    },
        )

        for test_input, want in tests:
            source = ""
            for name, body in test_input.iteritems():
                source = "%s{{define %s}}%s{{end}} " % (source, name, body)
            try:
                env = template.parse_templates('test', source)
                # pred is a template function that returns the predecessor of a
                # natural number for testing recursive templates.
                env.fns['pred'] = lambda x: x - 1
                escape.escape(env.templates, ('main',))
                got = env.with_data(data).sexecute('main')
            except:
                print >> sys.stderr, repr(source)
                raise

            if want != got:
                self.fail("want\n\t%r\ngot\n\t%r\n\n%s" % (want, got, env))


    def test_errors(self):
        tests = (
        # Non-error cases.
        (
            "{{if .Cond}}<a>{{else}}<b>{{end}}",
            None,
        ),
        (
            "{{if .Cond}}<a>{{end}}",
            None,
        ),
        (
            "{{if .Cond}}{{else}}<b>{{end}}",
            None,
        ),
        (
            "{{with .Cond}}<div>{{end}}",
            None,
        ),
        (
            "{{range .Items}}<a>{{end}}",
            None,
        ),
        (
            "<a href='/foo?{{range .Items}}&{{.K}}={{.V}}{{end}}'>",
            None,
        ),
        # Error cases.
        (
            "{{if .Cond}}<a{{end}}",
            "z:1: {{if}}: branches",
        ),
        (
            "{{if .Cond}}\n{{else}}\n<a{{end}}",
            "z:1: {{if}}: branches",
        ),
        (
            # Missing quote in the else branch.
            '{{if .Cond}}<a href="foo">{{else}}<a href="bar>{{end}}',
            "z:1: {{if}}: branches",
        ),
        (
            # Different kind of attribute: href implies a URL.
            "<a {{if .Cond}}href='{{else}}title='{{end}}{{.X}}'>",
            "z:1: {{if}}: branches",
        ),
        (
            "\n{{with .X}}<a{{end}}",
            "z:2: {{with}}: branches",
        ),
        (
            "\n{{with .X}}<a>{{else}}<a{{end}}",
            "z:2: {{with}}: branches",
        ),
        (
            "{{range .Items}}<a{{end}}",
            # TODO: Ideally this should mention that the problem occurs on
            # loop re-entry.
            'z:1: bad content in [Context STATE_TAG_NAME]: `<a`',
        ),
        (
            "\n{{range .Items}} x='<a{{end}}",
            ('z:2: {{range}}: loop switches between states'
             ' ([Context STATE_TAG_NAME],'
             ' [Context STATE_ATTR DELIM_SINGLE_QUOTE])'),
        ),
        (
            "<a b=1 c={{.H}}",
            ('template t does not end in the same context it starts:'
             ' [Context STATE_ATTR DELIM_SPACE_OR_TAG_END]'),
        ),
        (
            "<script>foo();",
            "template t does not end in the same context it starts",
        ),
        (
            '<a href="{{if .F}}/foo?a={{else}}/bar/{{end}}{{.H}}">',
            "z:1: {{.H}} appears in an ambiguous URL context",
        ),
        (
            "<a onclick=\"alert('Hello \\",
            r'''unfinished escape sequence in JS string: "Hello \\"''',
        ),
        (
            "<a onclick='alert(\"Hello\\, World\\",
            r'''unfinished escape sequence in JS string: "Hello\\, World\\"''',
        ),
        (
            "<a onclick=\'alert(/x+\\",
            r'''unfinished escape sequence in JS string: "x+\\"''',
        ),
        (
            r'''<a onclick="/foo[\]/''',
            r'''unfinished JS regexp charset: "foo[\\]/"''',
        ),
        (
            # It is ambiguous whether 1.5 should be 1\.5 or 1.5.
            # Either `var x = 1/- 1.5 /i.test(x)`
            # where `i.test(x)` is a method call of reference i,
            # or `/-1\.5/i.test(x)` which is a method call on a
            # case insensitive regular expression.
            ('<script>'
             '{{if false}}var x = 1{{end}}/-{{"1.5"}}/i.test(x)'
             '</script>'),
            "'/' could start a division or regexp: \"/-\"",
        ),
        (
            '{{template "foo"}}',
            "z:1: no such template foo",
        ),
        (
            '{{define "z"}}<div{{template "y"}}>{{end}}' +
                # Illegal starting in stateTag but not in stateText.
                '{{define "y"}} foo<b{{end}}',
            '"<" in attribute name: " foo<b"',
        ),
        (
            ('{{define "z"}}'
             '<script>reverseList = [{{template "t"}}]</script>'
             '{{end}}') +
             # Missing " after recursive call.
            ('{{define "t"}}'
             '{{if .Tail}}{{template "t" .Tail}}{{end}}{{.Head}}",'
             '{{end}}'),
            (': cannot compute output context for template '
             't$htmltemplate_stateJS_elementScript'),
        ),
        (
            '<input type=button value=onclick=>',
            'exp/template/html:z: "=" in unquoted attr: "onclick="',
        ),
        (
            '<input type=button value= onclick=>',
            'exp/template/html:z: "=" in unquoted attr: "onclick="',
        ),
        (
            '<input type=button value= 1+1=2>',
            'exp/template/html:z: "=" in unquoted attr: "1+1=2"',
        ),
        (
            "<a class=`foo>",
            "exp/template/html:z: \"`\" in unquoted attr: \"`foo\"",
        ),
        (
            "<a style=font:'Arial'>",
            'exp/template/html:z: "\'" in unquoted attr: "font:\'Arial\'"',
        ),
        (
            '<a=foo>',
            ': expected space, attr name, or end of tag, but got "=foo>"',
        ),
        )

        for test_input, want in tests:
            got = None
            try:
                env = template.parse_templates('z', test_input, 't')
                env = escape.escape(env.templates, ('t',))
            except escape.EscapeError, err:
                got = str(err)
            if want is None:
                if got is not None:
                    self.fail("input=%r: unexpected error %r" % (input, got))
                continue
            if got is None or got.find(want) == -1:
                self.fail(
                    ("input=%r: error\n"
                     "\t%r\n"
                     "does not contain expected string\n"
                     "\t%r")
                    % (test_input, got, want))


    def test_ensure_pipeline_contains(self):
        tests = (
        (
            "{{.X}}",
            "{{.X}}",
            (),
        ),
        (
            "{{.X | html}}",
            "{{.X | html}}",
            (),
        ),
        (
            "{{.X}}",
            "{{.X | html}}",
            ["html"],
        ),
        (
            "{{.X | html}}",
            "{{.X | html | urlquery}}",
            ["urlquery"],
        ),
        (
            "{{.X | html | urlquery}}",
            "{{.X | html | urlquery}}",
            ["urlquery"],
        ),
        (
            "{{.X | html | urlquery}}",
            "{{.X | html | urlquery}}",
            ["html", "urlquery"],
        ),
        (
            "{{.X | html | urlquery}}",
            "{{.X | html | urlquery}}",
            ["html"],
        ),
        (
            "{{.X | urlquery}}",
            "{{.X | html | urlquery}}",
            ["html", "urlquery"],
        ),
        (
            "{{.X | html | print}}",
            "{{.X | urlquery | html | print}}",
            ["urlquery", "html"],
        ),
        )
        for test_input, want, ids in tests:
            env = template.parse_templates('test', test_input, 'name')
            tmpl = env.templates['name']
            try:
                pipe = tmpl.to_pipeline()
            except:
                print >> sys.stderr, test_input
                raise

            escape.ensure_pipeline_contains(pipe, ids)
            got = str(tmpl.with_children((pipe.expr,)))
            if got != want:
                self.fail("%s, %r: want\n\t%s\ngot\n\t%s"
                          % (test_input, ids, want, got))

    def test_redundant_funcs(self):
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

        for n0, m in redundant_funcs:
            f0 = func_map[n0]
            for n1, _ in m:
                f1 = func_map[n1]
                for _, test_input in inputs:
                    want = f0(test_input)
                    got = f1(want)
                    if want != got:
                        self.fail(
                            "%s %s with %T %r: want\n\t%r,\ngot\n\t%r"
                            % (n0, n1, test_input, test_input, want, got))



if __name__ == '__main__':
    if len(sys.argv) == 2 and '-' == sys.argv[1]:
        def _tmpls_from_stdin():
            code = sys.stdin.read().decode('UTF-8')
            env = template.parse_templates('-', code, 'main')
            escape.escape(env.templates, ('main',))
            print env.sexecute('main')
        _tmpls_from_stdin()
    else:
        unittest.main()
