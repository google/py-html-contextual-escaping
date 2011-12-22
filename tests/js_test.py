#!/usr/bin/python

"""Testcases for module js"""

import content
import context
import debug
import escaping
import js
import math
import re
import unittest

class JsTest(unittest.TestCase):
    """Testcases for module js"""

    def test_is_regex_preceder(self):
        """Test heuristic that is used to update JS_CTX_*"""
        tests = (
            # Statement terminators precede regexps.
            (context.JS_CTX_REGEX, ";"),
            # This is not airtight.
            #     ({ valueOf: function () { return 1 } } / 2)
            # is valid JavaScript but in practice, devs do not do this.
            # A block followed by a statement starting with a RegExp is
            # much more common:
            #     while (x) {...} /foo/.test(x) || panic()
            (context.JS_CTX_REGEX, "}"),
            # But member, call, grouping, and array expression terminators
            # precede div ops.
            (context.JS_CTX_DIV_OP, ")"),
            (context.JS_CTX_DIV_OP, "]"),
            # At the start of a primary expression, array, or expression
            # statement, expect a regexp.
            (context.JS_CTX_REGEX, "("),
            (context.JS_CTX_REGEX, "["),
            (context.JS_CTX_REGEX, "{"),
            # Assignment operators precede regexps as do all exclusively
            # prefix and binary operators.
            (context.JS_CTX_REGEX, "="),
            (context.JS_CTX_REGEX, "+="),
            (context.JS_CTX_REGEX, "*="),
            (context.JS_CTX_REGEX, "*"),
            (context.JS_CTX_REGEX, "!"),
            # Whether the + or - is infix or prefix, it cannot precede a
            # div op.
            (context.JS_CTX_REGEX, "+"),
            (context.JS_CTX_REGEX, "-"),
            # An incr/decr op precedes a div operator.
            # This is not airtight. In (g = ++/h/i) a regexp follows a
            # pre-increment operator, but in practice devs do not try to
            # increment or decrement regular expressions.
            # (g++/h/i) where ++ is a postfix operator on g is much more
            # common.
            (context.JS_CTX_DIV_OP, "--"),
            (context.JS_CTX_DIV_OP, "++"),
            (context.JS_CTX_DIV_OP, "x--"),
            # When we have many dashes or pluses, then they are grouped
            # left to right.
            (context.JS_CTX_REGEX, "x---"), # A postfix -- then a -.
            # return followed by a slash returns the regexp literal or the
            # slash starts a regexp literal in an expression statement that
            # is dead code.
            (context.JS_CTX_REGEX, "return"),
            (context.JS_CTX_REGEX, "return "),
            (context.JS_CTX_REGEX, "return\t"),
            (context.JS_CTX_REGEX, "return\n"),
            (context.JS_CTX_REGEX, u"return\u2028"),
            # Identifiers can be divided and cannot validly be preceded by
            # a regular expressions. Semicolon insertion cannot happen
            # between an identifier and a regular expression on a new line
            # because the one token lookahead for semicolon insertion has
            # to conclude that it could be a div binary op and treat it as
            # such.
            (context.JS_CTX_DIV_OP, "x"),
            (context.JS_CTX_DIV_OP, "x "),
            (context.JS_CTX_DIV_OP, "x\t"),
            (context.JS_CTX_DIV_OP, "x\n"),
            (context.JS_CTX_DIV_OP, u"x\u2028"),
            (context.JS_CTX_DIV_OP, "preturn"),
            # Numbers precede div ops.
            (context.JS_CTX_DIV_OP, "0"),
            # Dots that are part of a number are div preceders.
            (context.JS_CTX_DIV_OP, "0."),
            )

        for want_ctx, js_code in tests:
            for start in (context.JS_CTX_REGEX, context.JS_CTX_DIV_OP,
                          context.JS_CTX_DIV_OP | context.STATE_JS):
                got = js.next_js_ctx(js_code, start)
                want = want_ctx | context.state_of(start)
                self.assertEquals(
                    want, got,
                    "%s: want %s got %s" % (
                        js_code,
                        debug.context_to_string(want),
                        debug.context_to_string(got)))

        self.assertEquals(
            context.STATE_JS | context.JS_CTX_REGEX,
            js.next_js_ctx("   ", context.STATE_JS | context.JS_CTX_REGEX),
            "Blank tokens")
        self.assertEquals(
            context.STATE_JS | context.JS_CTX_DIV_OP,
            js.next_js_ctx("   ", context.STATE_JS | context.JS_CTX_DIV_OP),
            "Blank tokens")


    def test_js_val_escaper(self):
        """Tests escape_js_value"""
        tests = (
            (int(42), " 42 "),
            (int(-42), " -42 "),
            (long(-42), " -42 "),
            (long(42), " 42 "),
            (1 << 53, " 9007199254740992 "),
            # ulp(1 << 53) > 1 so this loses precision in JS
            # but it is still a representable integer literal.
            ((long(1)<<53) + 1, " 9007199254740993 "),
            (float(1.0), " 1.0 "),
            (float(-1.0), " -1.0 "),
            (float(0.5), " 0.5 "),
            (float(-0.5), " -0.5 "),
            (float(1.0) / float(256), " 0.00390625 "),
            (float(0), " 0.0 "),
            (math.copysign(0.0, -1.0), " -0.0 "),
            ("", '""'),
            ("foo", '"foo"'),
            # Newlines.
            (u"\r\n\u2028\u2029", r'"\r\n\u2028\u2029"'),
            # "\v" == "v" on IE 6 so use "\x0b" instead.
            ("\t\x0b", r'"\t\u000b"'),
            (OrderedDict((("X", 1), ("Y", 2))), r'({"X":1,"Y":2})'),
            ([], "[]"),
            ((), "[]"),
            ([42, "foo", None], r'[42,"foo",null]'),
            (["<!--", "</script>", "-->"],
             r'["\x3c!--","\x3c/script\x3e","--\x3e"]'),
            ("<!--", r'"\x3c!--"'),
            ("-->", r'"--\x3e"'),
            ("<![CDATA[", r'"\x3c![CDATA["'),
            ("]]>", r'"]]\x3e"'),
            ("</script", r'"\x3c/script"'),
            (u"\U0001D11E", r'"\ud834\udd1e"'),
            )

        for test_input, want in tests:
            got = escaping.escape_js_value(test_input)
            self.assertEquals(
                want, got,
                "%r: want\n\t%r\ngot\n\t%r" % (test_input, want, got))

            # Make sure that escaping corner cases are not broken by nesting.
            want = "[%s]" % (re.sub(r'^[ (]|[) ]$', '', want))  # ({}) -> {}
            got = escaping.escape_js_value([test_input])
            self.assertEquals(
                want, got,
                "%r: want\n\t%r\ngot\n\t%r" % (test_input, want, got))

    def test_js_str_escaper(self):
        """Tests escape_js_string"""
        tests = (
            ("", r''),
            ("foo", r'foo'),
            (u"\u0000", r'\x00'),
            ("\t", r'\t'),
            ("\n", r'\n'),
            ("\r", r'\r'),
            (u"\u2028", r'\u2028'),
            (u"\u2029", r'\u2029'),
            ("\\", r'\\'),
            ("\\n", r'\\n'),
            ("foo\r\nbar", r'foo\r\nbar'),
            # Preserve attribute boundaries.
            ('"', r'\x22'),
            ("'", r'\x27'),
            # Allow embedding in HTML without further escaping.
            ('&amp;', r'\x26amp;'),
            # Prevent breaking out of text node and element boundaries.
            ("</script>", r'\x3c\/script\x3e'),
            ("<![CDATA[", r'\x3c![CDATA['),
            ("]]>", r']]\x3e'),
            # http://dev.w3.org/html5/markup/aria/syntax.html#escaping-text-span
            #   "The text in style, script, title, and textarea elements
            #   must not have an escaping text span start that is not
            #   followed by an escaping text span end."
            # Furthermore, spoofing an escaping text span end could lead
            # to different interpretation of a </script> sequence otherwise
            # masked by the escaping text span, and spoofing a start could
            # allow regular text content to be interpreted as script
            # allowing script execution via a combination of a JS string
            # injection followed by an HTML text injection.
            ("<!--", r'\x3c!--'),
            ("-->", r'--\x3e'),
            # From http://code.google.com/p/doctype/wiki/ArticleUtf7
            ("+ADw-script+AD4-alert(1)+ADw-/script+AD4-",
             r'\x2bADw-script\x2bAD4-alert(1)\x2bADw-\/script\x2bAD4-',
             ),
            # Invalid UTF-8 sequence
            ("foo\xA0bar", "foo\xA0bar"),
            # Invalid unicode scalar value.
            ("foo\xed\xa0\x80bar", "foo\xed\xa0\x80bar"),
            (content.SafeJSStr("\\r\\n"), "\\r\\n"),
            (content.SafeJSStr("O'Reilly"), "O\\x27Reilly"),
            # Orphaned slashes.
            (content.SafeJSStr("foo\\r\\nbar\\"), "foo\\r\\nbar\\\\"),
            (content.SafeJSStr("foo\\\r\nbar\\\\baz"),
             # \\\r\n treated as a line continuation which contributes
             # zero characters to the encoded string.
             "foo\\r\\nbar\\\\baz"),
            )

        for test_input, want in tests:
            got = escaping.escape_js_string(test_input)
            self.assertEquals(
                want, got, '%s\n\t%r\n!=\n\t%r' % (test_input, want, got))

    def test_js_regex_escaper(self):
        """Tests escape_js_regex"""
        tests = (
            ("", r'(?:)'),
            ("foo", r'foo'),
            (u"\u0000", r'\x00'),
            ("\t", r'\t'),
            ("\n", r'\n'),
            ("\r", r'\r'),
            (u"\u2028", r'\u2028'),
            (u"\u2029", r'\u2029'),
            ("\\", r'\\'),
            ("\\n", r'\\n'),
            ("foo\r\nbar", r'foo\r\nbar'),
            # Preserve attribute boundaries.
            ('"', r'\x22'),
            ("'", r'\x27'),
            # Allow embedding in HTML without further escaping.
            ('&amp;', r'\x26amp;'),
            # Prevent breaking out of text node and element boundaries.
            ("</script>", r'\x3c\/script\x3e'),
            ("<![CDATA[", r'\x3c!\x5bCDATA\x5b'),
            ("]]>", r'\x5d\x5d\x3e'),
            # Escaping text spans.
            ("<!--", r'\x3c!\x2d\x2d'),
            ("-->", r'\x2d\x2d\x3e'),
            ("*", r'\x2a'),
            ("+", r'\x2b'),
            ("?", r'\x3f'),
            ("[](){}", r'\x5b\x5d\x28\x29\x7b\x7d'),
            ("$foo|x.y", r'\x24foo\x7cx\x2ey'),
            ("x^y", r'x\x5ey'),
            )

        for test_input, want in tests:
            got = escaping.escape_js_regex(test_input)
            self.assertEquals(
                want, got, '%s\n\t%r\n!=\n\t%r' % (test_input, want, got))

    def test_escapers_on_lower7_plus(self):
        """Tests various js escapers on a bunch of codepoints"""
        test_input = (
            u"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f"
            u"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
            u" !\"#$%&'()*+,-./"
            u"0123456789:;<=>?"
            u"@ABCDEFGHIJKLMNO"
            u'PQRSTUVWXYZ[\\]^_'
            u"`abcdefghijklmno"
            u"pqrstuvwxyz{|}~\x7f"
            u"\u00A0\u0100\u2028\u2029\ufeff\U0001D11E")

        tests = (
            (
                escaping.escape_js_string,
                (u"\\x00\x01\x02\x03\x04\x05\x06\x07"
                 u"\\x08\\t\\n\\x0b\\f\\r\x0E\x0F"
                 u"\x10\x11\x12\x13\x14\x15\x16\x17"
                 u"\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
                 ur" !\x22#$%\x26\x27()*\x2b,-.\/"
                 ur"0123456789:;\x3c\x3d\x3e?"
                 ur"@ABCDEFGHIJKLMNO"
                 ur"PQRSTUVWXYZ[\\]^_"
                 ur"\x60abcdefghijklmno"
                 ur"pqrstuvwxyz{|}~\x7f"
                 u"\u00A0\u0100\\u2028\\u2029\ufeff\U0001D11E"),
                ),
            (
                escaping.escape_js_regex,
                (u"\\x00\x01\x02\x03\x04\x05\x06\x07"
                 u"\\x08\\t\\n\\x0b\\f\\r\x0E\x0F"
                 u"\x10\x11\x12\x13\x14\x15\x16\x17"
                 u"\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
                 ur" !\x22#\x24%\x26\x27\x28\x29\x2a\x2b,\x2d\x2e\/"
                 ur"0123456789\x3a;\x3c\x3d\x3e\x3f"
                 ur"@ABCDEFGHIJKLMNO"
                 ur"PQRSTUVWXYZ\x5b\\\x5d\x5e_"
                 ur"\x60abcdefghijklmno"
                 ur"pqrstuvwxyz\x7b\x7c\x7d~\x7f"
                 u"\u00A0\u0100\\u2028\\u2029\ufeff\U0001D11E"),
                ),
            )

        for escaper, want in tests:
            got = escaper(test_input)
            self.assertEquals(
                want, got,
                '%s: want\n\t%r\n!=\n\t%r' % (escaper.__name__, want, got))

            # Escape it rune by rune to make sure that any
            # fast-path checking does not break escaping.
            out = ''
            for char in test_input:
                out += escaper(char)
            self.assertEquals(want, out, 'rune-wise %s' % escaper.__name__)


class OrderedDict(dict):
    """
    Enough of collections.OrderedDict to get make testing of the JSON encoding
    of ({'X': ..., 'Y': ...}) stable across python interpreters.
    """
    def __init__(self, pairs):
        dict.__init__(self, pairs)
        self.pairs = pairs

    def items(self):
        return list(self.pairs)

    def iteritems(self):
        return list(self.pairs)

    def keys(self):
        return [a for a, _ in self.pairs]

    def iterkeys(self):
        return [a for a, _ in self.pairs]


if __name__ == '__main__':
    unittest.main()
