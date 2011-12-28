#!/usr/bin/python

"""Unit tests for module escape"""

import content
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


class EscapeTest(unittest.TestCase):
    """
    Test the contextual autoescaping function using the template module
    as the template implementation.
    """
    
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

        tests = (
            (
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
                "<a href='{{'/foo/bar?a=b&c=d'}}'>",
                "<a href='/foo/bar?a=b&amp;c=d'>",
                ),
            (
                "urlStartAbsOk",
                r"<a href='{{'http://example.com/foo/bar?a=b&c=d'}}'>",
                "<a href='http://example.com/foo/bar?a=b&amp;c=d'>",
                ),
            (
                "protocolRelativeURLStart",
                "<a href='{{'//example.com:8000/foo/bar?a=b&c=d'}}'>",
                "<a href='//example.com:8000/foo/bar?a=b&amp;c=d'>",
                ),
            (
                "pathRelativeURLStart",
                '<a href="{{"/javascript:80/foo/bar"}}">',
                '<a href="/javascript:80/foo/bar">',
                ),
            (
                "dangerousURLStart",
                "<a href='{{'javascript:alert(%22pwned%22)'}}'>",
                "<a href='#zSafehtmlz'>",
                ),
            (
                "dangerousURLStart2",
                "<a href='  {{\"javascript:alert(%22pwned%22)\"}}'>",
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
                "<a href='http://{{'javascript:80'}}/foo'>",
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
                "<button onclick='alert(1/ null in numbers)'>",
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
                '<a style="background: url(\'{{"javascript:alert(1337)"}}\')">',
                '<a style="background: url(\'#zSafehtmlz\')">',
                ),
            (
                "styleStrBadProtocolBlocked",
                r"""<a style="background: '{{"vbscript:alert(1337)"}}'">""",
                r"""<a style="background: '#zSafehtmlz'">""",
                ),
            (
                "styleStrEncodedProtocolEncoded",
                ('<a style="background:'
                 r"'{{'javascript\\3a alert(1337)'}}'"
                 '">'),
                # The CSS string 'javascript\\3a alert(1337)' does not contain
                # a colon.
                ('<a style="background:'
                 r"'javascript\\3a alert\28 1337\29 '"
                 '">'),
                ),
            (
                "styleURLGoodProtocolPassed",
                ('<a style="background: url('
                 "'{{\"http://oreilly.com/O'Reilly Animals(1)<2>;{}.html\"}}'"
                 ')">'),
                ('<a style="background: url('
                 "'http://oreilly.com/"
                 "O%27Reilly%20Animals%281%29%3c2%3e;%7b%7d.html'"
                 ')">'),
                ),
            (
                "styleStrGoodProtocolPassed",
                ("<a style=\"background:"
                 " '{{\"http://oreilly.com/O'Reilly Animals(1)<2>;{}.html\"}}'"
                 '">'),
                (r'<a style="background:'
                 r" 'http\3a \2f \2f oreilly.com\2f "
                 r"O\27 Reilly Animals\28 1\29 \3c 2\3e "
                 r"\3b \7b \7d .html'"
                 r'">'),
                ),
            (
                "styleURLEncodedForHTMLInAttr",
                ('<a style="background: url('
                 "'{{'/search?img=foo&size=icon'}}')\">"),
                ('<a style="background: url('
                 "'/search?img=foo&amp;size=icon')\">"),
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
                "sltyleURLSpecialsEncoded",
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
                 " 'http://www.example.com/"
                 "?q=%2f%2a%2a%2f%27%22%3b%3a%2f%2f%20%5c'"
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
                ("<b>Hello, <!-- name of "
                 "{{if .T}}city -->{{.C}}{{else}}world -->"
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
                ("<script>for (;;) { if (c()) break/* foo not a label\n"
                 " */foo({{.T}});}</script>"),
                # Newline separates break from call. If newline
                # removed, then break will consume label leaving
                # code invalid.
                ("<script>for (;;) { if (c()) break \n"
                 "foo( true );}</script>"),
                ),
            (
                "JS single-line block comment",
                ("<script>for (;;) {\n"
                 "if (c()) break/* foo a label */foo;"
                 "x({{.T}});}</script>"),
                # Newline separates break from call. If newline
                # removed, then break will consume label leaving
                # code invalid.
                ("<script>for (;;) {\n"
                 "if (c()) break foo;"
                 "x( true );}</script>"),
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
                ("<style>p// paragraph\n"
                 '{border: 1px/* color */{{"#00f"}}}</style>'),
                ("<style>p\n"
                 "{border: 1px #00f}</style>"),
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
                ('&iexcl;<b class="foo">Hello</b>,'
                 ' <textarea>O\'World</textarea>!'),
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
                ('<textarea>'
                 '&iexcl;&lt;b class=&#34;foo&#34;&gt;Hello&lt;/b&gt;,'
                 ' &lt;textarea&gt;O&#39;World&lt;/textarea&gt;!'
                 '</textarea>'),
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
                '{{"10$"}}<{{"script src,evil.org/pwnd.js"}}>...',
                '10$<zSafehtmlz>...',
                ),
            (
                "No comment injection",
                '<{{"!--"}} {{"--"}}>',
                '<zSafehtmlz -->',  # Or <zSafehtmlz
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
                 ' src="?%3ciconPath%3e"title="&lt;title&gt;"'
                 ' alt="&lt;alt&gt;">'),
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
                '<{{"h3"}}><table><{{"thead"}}>...</{{"h3"}}>',
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
                '<zSafehtmlz>doEvil()</zSafehtmlz>',
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
        """
        Test cases involving multiple and recursive templates.
        """
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
                source = "%s{{define %r}}%s{{end}} " % (source, name, body)
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
        """
        Check reported error messages.
        """
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
            ('template z does not start and end in the same context:'
             ' [Context STATE_ATTR DELIM_SPACE_OR_TAG_END]'),
        ),
        (
            "<script>foo();",
            "template z does not start and end in the same context",
        ),
        (
            '<a href="{{if .F}}/foo?a={{else}}/bar/{{end}}{{.H}}">',
            "z:1: {{.H}}: hole appears in an ambiguous URL context",
        ),
        (
            "<a onclick=\"alert('Hello \\",
            (r"z:1: bad content in [Context STATE_JS DELIM_DOUBLE_QUOTE]:"
             r" `alert('Hello \`"),
        ),
        (
            "<a onclick='alert(\"Hello\\, World\\",
            (r'z:1: bad content in [Context STATE_JS DELIM_SINGLE_QUOTE]:'
             r' `alert("Hello\, World\`'),
        ),
        (
            "<a onclick='alert(/x+\\",
            (r'z:1: bad content in [Context STATE_JS DELIM_SINGLE_QUOTE]:'
             r' `alert(/x+\`'),
        ),
        (
            '<a onclick="/foo[\]/',
            r'template z does not start and end in the same context:',
        ),
        (
            # It is ambiguous whether 1.5 should be 1\.5 or 1.5.
            # Either `var x = 1/- 1.5 /i.test(x)`
            # where `i.test(x)` is a method call of reference i,
            # or `/-1\.5/i.test(x)` which is a method call on a
            # case insensitive regular expression.
            ('<script>'
             '{{if False}}var x = 1{{end}}/-{{"1.5"}}/i.test(x)'
             '</script>'),
            ('ambiguous / could start a division or a RegExp.'
             '  Please parenthesize near `/-`.'),
        ),
        (
            '{{template "foo"}}',
            "z:1: no such template foo",
        ),
        (
            '{{define "z"}}<div{{template "y"}}>{{end}}' +
                # Illegal starting in stateTag but not in stateText.
                '{{define "y"}} foo<b{{end}}',
            'bad content in [Context STATE_TAG]: `<b`',
        ),
        (
            ('{{define "z"}}'
             '<script>reverseList = [{{template "t"}}]</script>'
             '{{end}}') +
             # Missing " after recursive call.
            ('{{define "t"}}'
             '{{if .Tail}}{{template "t" .Tail}}{{end}}{{.Head}}",'
             '{{end}}'),
            (': cannot compute output context for template t in'
             ' [Context STATE_JS ELEMENT_SCRIPT]'),
        ),
        (
            "<input type=button value=onclick=>",
            "z:1: '=' in unquoted attr: 'onclick='",
        ),
        (
            '<input type=button value= onclick=>',
            "z:1: '=' in unquoted attr: 'onclick='",
        ),
        (
            "<input type=button value= 1+1=2>",
            "z:1: '=' in unquoted attr: '1+1=2'",
        ),
        (
            "<a class=`foo>",
            "z:1: bad content in [Context STATE_BEFORE_VALUE]: ``foo>`",
        ),
        (
            "<a style=font:'Arial'>",
            'z:1: "\'" in unquoted attr: "font:\'Arial\'"',
        ),
        (
            '<a=foo>',
            'z:1: bad content in [Context STATE_TAG_NAME]: `=foo>`',
        ),
        )

        for test_input, want in tests:
            got = None
            try:
                env = template.parse_templates('z', test_input, 'z')
                escape.escape(env.templates, ('z',))
            except escape.EscapeError, err:
                got = str(err)
            except:
                print '\ntest_errors: %s' % test_input
                raise
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
        """
        Test the interaction between existing escaping directives and those
        required by the contextual escaper.
        """
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


if __name__ == '__main__':
    unittest.main()
