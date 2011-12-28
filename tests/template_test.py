#!/usr/bin/python

"""
Tests for template module.
"""

import StringIO
import sys
import template
import unittest

class TemplateTest(unittest.TestCase):
    """
    Tests the parser and renderer and execute.
    """

    def test_parsing_and_execution(self):
        test_input = {
            'foo': 'bar',
            'foo1': { 'foo2': '_FOO2_' },
            'boo': ('baz1', 'baz2'),
            'far': 42,
            'empty': (),
            }

        fns = {
            'min': min,
            'max': max,
            'succ': lambda x: x + 1,
            'ucase': lambda s: s.upper(),
            'world': lambda: 'world',
            }

        tests = (
            (
                # Template code.
                "",
                # Template parseable form.
                "{{define 'main'}}{{end}}",
                # Result of executing the template named "main" with test_input.
                "",
                ),
            (
                "Hello, World!",
                "{{define 'main'}}Hello, World!{{end}}",
                "Hello, World!",
                ),
            (
                "Hello, {{'World'}}!",
                "{{define 'main'}}Hello, {{'World'}}!{{end}}",
                "Hello, World!",
                ),
            (
                'Hello, {{"World"}}!',
                "{{define 'main'}}Hello, {{'World'}}!{{end}}",
                "Hello, World!",
                ),
            (
                r'Hello, {{"\x57orld"}}!',
                "{{define 'main'}}Hello, {{'World'}}!{{end}}",
                "Hello, World!",
                ),
            (
                "Hello{{if .Wld}}, {{end}}{{.Wld}}!",
                "{{define 'main'}}Hello{{if .Wld}}, {{end}}{{.Wld}}!{{end}}",
                "Hello!",
                ),
            (
                "{{.foo}},{{.foo1.foo2}},{{.foo.nosuchfoo}},{{.nosuchfoo.foo}}",
                ("{{define 'main'}}"
                 "{{.foo}},{{.foo1.foo2}},{{.foo.nosuchfoo}},{{.nosuchfoo.foo}}"
                 "{{end}}"),
                "bar,_FOO2_,,",
                ),
            (
                "{{min(10,42)}},{{max(10,42)}},{{succ(10)}},{{42 | succ}}",
                ("{{define 'main'}}"
                 "{{min(10, 42)}},{{max(10, 42)}},{{10 | succ}},{{42 | succ}}"
                 "{{end}}"),
                "10,42,11,43",
                ),
            (
                "Hello, {{world()}}!",
                "{{define 'main'}}Hello, {{world()}}!{{end}}",
                "Hello, world!",
                ),
            (
                ("{{define 'helper'}}Hello, {{.}}!{{end}}"
                 "{{with 'World'}}{{template 'helper'}}{{end}}"),
                ("{{define 'helper'}}Hello, {{.}}!{{end}}\n\n"
                 "{{define 'main'}}"
                 "{{with 'World'}}{{template 'helper'}}{{end}}"
                 "{{end}}"),
                "Hello, World!",
                ),
            (
                ("{{define 'helper'}}Hello, {{.}}!{{end}}"
                 "{{template 'helper' 'World'}}"),
                ("{{define 'helper'}}Hello, {{.}}!{{end}}\n\n"
                 "{{define 'main'}}"
                 "{{template 'helper' 'World'}}"
                 "{{end}}"),
                "Hello, World!",
                ),
            (
                ("{{define 'helper'}}Hello, {{.}}!{{end}}\n\n"
                 "{{template 'helper' 'World' | ucase}}"),
                ("{{define 'helper'}}Hello, {{.}}!{{end}}\n\n"
                 "{{define 'main'}}"
                 "{{template 'helper' 'World' | ucase}}"
                 "{{end}}"),
                "Hello, WORLD!",
                ),
            (
                "{{if True}}a{{else}}b{{end}}",
                "{{define 'main'}}{{if True}}a{{else}}b{{end}}{{end}}",
                "a",
                ),
            (
                "{{if False}}a{{else}}b{{end}}",
                "{{define 'main'}}{{if False}}a{{else}}b{{end}}{{end}}",
                "b",
                ),
            (
                "{{if True}}a{{end}}",
                "{{define 'main'}}{{if True}}a{{end}}{{end}}",
                "a",
                ),
            (
                "{{if False}}a{{end}}",
                "{{define 'main'}}{{if False}}a{{end}}{{end}}",
                "",
                ),
            (
                "{{with .foo1}}{{.foo2}}{{else}}Empty{{end}}",
                ("{{define 'main'}}"
                 "{{with .foo1}}{{.foo2}}{{else}}Empty{{end}}"
                 "{{end}}"),
                "_FOO2_"),
            (
                "{{with .foo1}}{{.foo2}}{{end}}",
                ("{{define 'main'}}"
                 "{{with .foo1}}{{.foo2}}{{end}}"
                 "{{end}}"),
                "_FOO2_"),
            (
                "{{with .nosuchfoo}}{{.foo2}}{{else}}Empty{{end}}",
                ("{{define 'main'}}"
                 "{{with .nosuchfoo}}{{.foo2}}{{else}}Empty{{end}}"
                 "{{end}}"),
                "Empty"),
            (
                "{{with .nosuchfoo}}{{.foo2}}{{end}}",
                ("{{define 'main'}}"
                 "{{with .nosuchfoo}}{{.foo2}}{{end}}"
                 "{{end}}"),
                ""),
            (
                "{{range .boo}}{{.}}.{{else}}Empty{{end}}",
                ("{{define 'main'}}"
                 "{{range .boo}}{{.}}.{{else}}Empty{{end}}"
                 "{{end}}"),
                "baz1.baz2."),
            (
                "{{range .boo}}{{.}}.{{end}}",
                ("{{define 'main'}}"
                 "{{range .boo}}{{.}}.{{end}}"
                 "{{end}}"),
                "baz1.baz2."),
            (
                "{{range .empty}}{{.}}.{{else}}Empty{{end}}",
                ("{{define 'main'}}"
                 "{{range .empty}}{{.}}.{{else}}Empty{{end}}"
                 "{{end}}"),
                "Empty"),
            (
                "{{range .empty}}{{.}}.{{end}}",
                ("{{define 'main'}}"
                 "{{range .empty}}{{.}}.{{end}}"
                 "{{end}}"),
                ""),
            (
                "{{1}} {{1.5}} {{0x10}} {{+1e3}} {{-1}} {{1e-1}}",
                ("{{define 'main'}}"
                 "{{1}} {{1.5}} {{16}} {{1000.0}} {{-1}} {{0.1}}"
                 "{{end}}"),
                "1 1.5 16 1000.0 -1 0.1"),
            )

        for code, norm, want in tests:
            try:
                env = template.parse_templates('src', code, 'main')
                self.assertEquals(norm, str(env))

                env2 = template.Env()
                env2.parse_templates(template.Loc('src'), norm)
                self.assertEquals(norm, str(env2))

                self.assertEquals(
                    want,
                    env.with_data(test_input).with_fns(fns).sexecute('main'))

                buf = StringIO.StringIO()
                env2.with_data(test_input).with_fns(fns).execute('main', buf)
                self.assertEquals(want, buf.getvalue())
            except:
                print >> sys.stderr, code
                raise

    def test_error_messages(self):
        tests = (
            (
                '{{define}}',
                'src:1: missing expression part at end of input',
                ),
            (
                '\n{{define}}',
                'src:2: missing expression part at end of input',
                ),
            (
                ' {{define 42}}',
                'src:1: expected quoted template name, not 42',
                ),
            (
                '{{define "x"}}x{{end}}\n\n{{define "x"}}y{{end}}',
                "src:3: redefinition of 'x'",
                ),
            (
                'Hello, World!\n{{end}}',
                'src:2: unparsed content {{end}}',
                ),
            (
                '{{"foo}}',
                'src:1: malformed string literal "foo',
                ),
            (
                "{{'foo}}",
                "src:1: malformed string literal 'foo",
                ),
            (
                "\n{{'foo}}",
                "src:2: malformed string literal 'foo",
                ),
            (
                "{{min(1, 2}}",
                "src:1: expected ) at end of input",
                ),
            (
                "{{}}",
                "src:1: missing expression part at end of input",
                ),
            (
                "{{1n}}",
                "src:1: expected function name but got 1n",
                ),
            (
                r"{{'\'}}",
                r"src:1: invalid string literal '\'",
                ),
            (
                "{{.x | y z}}",
                "src:1: trailing content in expression: .x | y ^z",
                ),
            )
        for code, err_msg in tests:
            try:
                env = template.parse_templates('src', code, 'main')
            except template.ParseError, err:
                got = str(err)
                self.assertEquals(err_msg, got)
                continue
            self.fail('Successfully parsed %r to %r' % (code, str(env)))

if __name__ == '__main__':
    unittest.main()
