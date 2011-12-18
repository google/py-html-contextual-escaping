#!/usr/bin/python

"""
An implementation of enough of Go templates to enable testing.
"""

import cStringIO as StringIO
import re


# Functions available by default.
_BUILTINS = {}


class Env(object):
    """The environment in which a template is executed."""

    def __init__(self, data, fns, templates):
        self.data = data
        self.fns = fns
        self.templates = templates

    def with_data(self, data):
        """
        Returns an environment with the same functions and templates but
        with the given data value.
        """
        return Env(data=data, fns=self.fns, templates=self.templates)

    def execute(self, name, out):
        """
        Executes the named template in this environment appending
        its output to out.
        """
        self.templates[name].execute(self, out)

    def sexecute(self, name):
        """
        Returns the result of executing the named template as a string.
        """
        buf = StringIO.StringIO()
        self.templates[name].execute(self, buf)
        return buf.getvalue()

    def __str__(self):
        """
        Returns a form parseable by parse_templates.
        """
        return '\n\n'.join(
            [("{{define %s}}%s{{end}}" % (name, body))
             for (name, body) in self.templates.iteritems()])


class Node(object):
    """
    Abstract base class for a tree-interpreted template.
    """

    def __init__(self, src, line):
        self.src = src
        self.line = line

    def execute(self, env, out):
        """
        Appends output to out if a statement node,
        or returns the value if an expression node.
        """
        raise Exception("Not overridden")

    def clone(self):
        """A structural copy"""
        raise Exception("Not overridden")

    def __str__(self):
        raise Exception("Not overridden")


class TextNode(Node):
    """
    A chunk of literal text in the template.
    """

    def __init__(self, src, line, text):
        Node.__init__(self, src, line)
        assert type(text) in (str, unicode)
        self.text = text

    def execute(self, env, out):
        out.write(self.text)

    def clone(self):
        return TextNode(self.src, self.line, self.text)

    def __str__(self):
        return self.text


class InterpolationNode(Node):
    """An interpolation of an untrusted expression"""

    def __init__(self, src, line, expr):
        Node.__init__(self, src, line)
        self.expr = expr

    def execute(self, env, out):
        value = self.expr.execute(env, None)
        if value is not None:
            if type(value) not in (str, unicode):
                value = str(value)
            out.write(value)

    def clone(self):
        return InterpolationNode(self.src, self.line, self.expr.clone())

    def __str__(self):
        return "{{%s}}" % self.expr


class ReferenceNode(Node):
    """
    An expression node (a node that execute()s to a return value)
    whose value is determined soley by property lookups on the data value.
    """

    def __init__(self, src, line, properties):
        Node.__init__(self, src, line)
        self.properties = tuple(properties)

    def execute(self, env, out):
        data = env.data
        for prop in self.properties:
            if data is None:
                break
            data = data.get(prop)
        return data

    def clone(self):
        return ReferenceNode(self.src, self.line, self.properties)

    def __str__(self):
        return ".%s" % '.'.join(self.properties)


class CallNode(Node):
    """An function call"""

    def __init__(self, src, line, name, args):
        Node.__init__(self, src, line)
        self.name = name
        self.args = tuple(args)

    def execute(self, env, out):
        return env.fns[self.name](
            *[arg.execute(env, out) for arg in self.args])

    def clone(self):
        return CallNode(
            self.src, self.line, [arg.clone() for arg in self.args])

    def __str__(self):
        if len(self.args) == 1:
            return "%s | %s" % (str(self.args[0]), self.name)
        else:
            return '%s(%s)' % (
                self.name, ", ".join([str(arg) for arg in self.args]))


class StrLitNode(Node):
    """A string literal in an expression"""

    def __init__(self, src, line, value):
        Node.__init__(self, src, line)
        if type(value) not in (str, unicode):
            value = str(value)
        self.value = value

    def execute(self, env, out):
        return self.value

    def clone(self):
        return StrLitNode(self.src, self.line, self.value)

    def __str__(self):
        return repr(self.value)


class TemplateNode(Node):
    """A call to another template."""

    def __init__(self, src, line, name, expr):
        Node.__init__(self, src, line)
        self.name = name
        self.expr = expr

    def execute(self, env, out):
        name = self.name.execute(env)
        if self.expr:
            env = env.with_data(self.expr.execute(env, None))
        env.templates[name].execute(env, out)

    def clone(self):
        expr = self.expr
        if expr:
            expr = expr.clone()
        return TemplateNode(self.src, self.line, self.name.clone(), expr)

    def __str__(self):
        expr = self.expr
        expr_str = ""
        if expr:
            expr_str = " %s" % self.expr
        return "{{template %s%s}}" % (self.name, expr_str)


class WithNode(Node):
    """Executes body in a more specific data context."""

    def __init__(self, src, line, expr, body, else_clause):
        Node.__init__(self, src, line)
        self.expr = expr
        self.body = body
        self.else_clause = else_clause

    def execute(self, env, out):
        data = self.expr.execute(env, None)
        if data:
            self.body.execute(env.with_data(data), out)
        elif self.else_clause:
            self.else_clause.execute(env, out)

    def clone(self):
        expr = self.expr.clone()
        body = self.body.clone()
        else_clause = self.else_clause
        if else_clause:
            else_clause = else_clause.clone()
        return WithNode(self.src, self.line, expr, body, else_clause)

    def __str__(self):
        else_clause = self.else_clause
        if else_clause:
            return "{{with %s}}%s{{else}}%s{{end}}" % (
                self.expr, self.body, else_clause)
        return "{{with %s}}%s{{end}}" % (self.expr, self.body)


class IfNode(Node):
    """Conditional."""

    def __init__(self, src, line, expr, then_clause, else_clause):
        Node.__init__(self, src, line)
        self.expr = expr
        self.then_clause = then_clause
        self.else_clause = else_clause

    def execute(self, env, out):
        if self.expr.execute(env, None):
            self.then_clause.execute(env, out)
        elif self.else_clause:
            self.else_clause.execute(env, out)

    def clone(self):
        expr = self.expr.clone()
        then_clause = self.then_clause.clone()
        else_clause = self.else_clause
        if else_clause:
            else_clause = else_clause.clone()
        return IfNode(self.src, self.line, expr, then_clause, else_clause)

    def __str__(self):
        else_clause = self.else_clause
        if else_clause:
            return "{{if %s}}%s{{else}}%s{{end}}" % (
                self.expr, self.then_clause, else_clause)
        return "{{if %s}}%s{{end}}" % (self.expr, self.then_clause)


class RangeNode(Node):
    """Loop."""

    def __init__(self, src, line, expr, body, else_clause):
        Node.__init__(self, src, line)
        self.expr = expr
        self.body = body
        self.else_clause = else_clause

    def execute(self, env, out):
        iterable = self.expr.execute(env, None)
        if iterable:
            for value in iterable:
                self.body.execute(env.with_data(value), out)
        elif self.else_clause:
            self.else_clause.execute(env, out)

    def clone(self):
        expr = self.expr.clone()
        body = self.body.clone()
        else_clause = self.else_clause
        if else_clause:
            else_clause = else_clause.clone()
        return RangeNode(self.src, self.line, expr, body, else_clause)

    def __str__(self):
        else_clause = self.else_clause
        if else_clause:
            return "{{range %s}}%s{{else}}%s{{end}}" % (
                self.expr, self.body, else_clause)
        return "{{range %s}}%s{{end}}" % (self.expr, self.body)


class ListNode(Node):
    """The concatenation of a series of nodes."""

    def __init__(self, src, line, children):
        Node.__init__(self, src, line)
        self.children = tuple(children)

    def execute(self, env, out):
        for child in self.children:
            child.execute(env, out)

    def clone(self):
        return ListNode(
            self.src, self.line, [child.clone() for child in self.children])

    def __str__(self):
        return ''.join([str(child) for child in self.children])


def parse_templates(src, code, name=None):
    """
    Parses a template definition or set of template definitions
    to an environment.

    This is the dual of env.__str__.
    """

    # Normalize newlines.
    code = re.sub(r'\r\n?', '\n', code)

    env = Env(None, _BUILTINS, {})

    # Split src into a run of non-{{...}} tokens with
    # {{...}} constructs in-between.
    # Inside a {{...}}, '}}' can appear inside a quoted string but not
    # elsewhere.  Quoted strings are \-escaped.
    tokens = re.split(
        r'(\{\{(?:'
        r'[^\x22\x27\}]'
        r'|\x22(?:[^\\\x22]|\\.)*\x22'
        r'|\x27(?:[^\\\x22]|\\.)*\x27'
        r')*\}\})', code)

    # For each token, the line on which it appears.
    lines = []
    line = 0
    print repr(tokens)
    for token in tokens:
        lines.append(line)
        line += len(token.split('\n')) - 1
    # Put an entry at the end, so the list is indexable by end-of-input.
    lines.append(line)

    # White-space at the end is ignorable.
    # Loop below ignores white-space at the start.
    while len(tokens) and not tokens[-1].strip():
        tokens = tokens[:-1]

    # The inner functions below comprise a recursive descent parser for the
    # template grammar.
    def fail(pos, msg):
        """Generate an exception with source and line info"""
        raise Exception('%s:%s: %s' % (src, lines[pos], msg))

    def expect(pos, token):
        """Advance one token if it matches or fail with an error message."""
        if pos == len(tokens):
            fail(pos, 'Expected %s at end of input' % token)
        if tokens[pos] != token:
            fail(pos, 'Expected %s, got %s' % (token, tokens[pos]))
        return pos + 1

    def parse_define(pos):
        """Parses a {{{define}}}...{{end}} to update env.templates"""
        token = tokens[pos]
        expr = parse_expr(pos, token[len('{{define'):-2])
        # TODO: error on {{definefoo}}
        name = expr.execute(Env(None, {}, {}))
        if name is None:
            fail(pos, "expected name as quoted string, not %s" % expr)
        pos = define(name, pos+1)
        pos = expect(pos, '{{end}}')
        return pos

    def define(name, pos):
        """Updated env.templates[name] or fails with an informative error"""
        body, pos = parse_list(pos)
        if name in env.templates:
            fail(pos, 'Redefinition of %r' % name)
        env.templates[name] = body
        return pos

    def parse_list(pos):
        """Parses a series of statement nodes."""
        line = lines[pos]
        children = []
        while pos < len(tokens):
            atom, pos = parse_atom(pos)
            if atom is None:
                break
            children.append(atom)
        if len(children) == 1:
            return children[0], pos
        return ListNode(src, line, children), pos

    def parse_atom(pos):
        """Parses a single full statement node."""
        if pos == len(tokens):
            return None
        token = tokens[pos]
        match = re.search(
            r'^\{\{(?:(if|range|with|template|end|else)\b)?(.*)\}\}$', token)
        if not match:
            return TextNode(src, lines[pos], token), pos+1
        name = match.group(1)
        if not name:
            return InterpolationNode(
                src, lines[pos], parse_expr(pos, token[2:-2])), pos+1
        if name in ('end', 'else'):
            return None, pos
        if name == 'template':
            name_and_data = match.group(2)
            template_name, name_and_data = parse_expr_prefix(
                lines[pos], name_and_data)
            expr = None
            if name_and_data.strip():
                # TODO: wrong line number if there are linebreaks in the name
                # portion.
                expr = parse_expr(pos, name_and_data)
            return TemplateNode(src, lines[pos], template_name, expr), pos+1
        return parse_block(name, pos, parse_expr(pos, match.group(2)))

    def parse_block(name, pos, expr):
        body, tpos = parse_list(pos+1)
        else_clause = None
        if tpos < len(tokens) and tokens[tpos] == '{{else}}':
            else_clause, tpos = parse_list(tpos + 1)
        tpos = expect(tpos, '{{end}}')
        if name == 'if':
            ctor = IfNode
        elif name == 'range':
            ctor = RangeNode
        else:
            assert name == 'with'
            ctor = WithNode
        return ctor(src, lines[pos], expr, body, else_clause), tpos

    def parse_expr(pos, expr_text):
        """Parse an expression"""
        expr, remainder = parse_expr_prefix(lines[pos], expr_text)
        if remainder:
            fail(pos, 'Trailing content in expression: %s' % remainder)
        return expr

    def parse_expr_prefix(line, expr_text):
        """
        Parse an expression from the front of the given text returning
        it and the remaining text.
        """
       
        line_ref = [line]
        etokens = re.findall(
            (r'[^\t\n\r \x27\x22()\|,]+'  # A run of non-breaking characters.
             r'|[\t\n\r ]+'  # Whitespace
             r'|[()\|,]'  # Punctuation
             r'|\x27(?:[^\\\x27]|\\.)\x27'  # '...'
             r'|\x22(?:[^\\\x22]|\\.)\x22'),  # "..."
            expr_text)

        def skip_ignorable(epos):
            """Consumes white-space tokens"""
            while epos < len(etokens) and not etokens[epos].strip():
                line_ref[0] += len(etokens[epos].split('\n')) - 1
                epos += 1
            return epos

        def fail(msg):
            raise Exception('%s:%s: %s' % (src, line_ref[0], msg))

        def expect(epos, token):
            """Advance one token if it matches or fail with an error message."""
            if epos == len(etokens):
                fail('Expected %s at end of input' % token)
            if tokens[epos] != token:
                fail('Expected %s, got %s' % (token, tokens[epos]))
            return epos + 1

        # There are two precedence levels.
        # highest - string literals, references, calls
        # lowest  - pipelines
        epos = 0

        def parse_pipeline(epos):
            expr, epos = parse_atom(epos)
            epos = skip_ignorable(epos)
            while epos < len(etokens) and etokens[epos] == '|':
                right = parse_name(epos)
                expr = CallNode(src, expr.line, right, (expr,))
                epos = skip_ignorable(epos + 1)
            return expr, epos

        def parse_atom(epos):
            epos = skip_ignorable(epos)
            if epos == len(etokens):
                fail('missing expression part at end of %s' % expr_text)
            etoken = etokens[epos]
            ch0 = etoken[0]
            if ch0 == '.':  # Reference
                return (ReferenceNode(src, line_ref[0], etoken[1].split('.')),
                        epos+1)
            if ch0 in ('"', "'"):
                return (StrLitNode(src, line_ref[0], unescape(etoken)),
                        epos+1)
            # Assume a function call.
            line = line_ref[0]
            name = parse_name(epos)
            epos = skip_ignorable(epos + 1)
            epos = expect(epos, '(')
            epos = skip_ignorable(epos + 1)
            args = []
            if epos < len(etokens) and etokens[epos] != ')':
                while True:
                    arg, epos = parse_pipeline(epos)
                    args.append(arg)
                    epos = skip_ignorable(epos)
                    if epos == len(etokens) or etokens[epos] != ',':
                        break
                    epos += 1
            epos = expect(epos, ')')
            return CallNode(src, line, name, args), epos

        def parse_name(epos):
            """
            Returns the value of the identifier token at etokens[epos]
            or fails with a useful error message.
            """
            if epos == len(etokens):
                fail('missing function name at end of %s' % expr_text)
            etok = etokens[epos]
            if not re.search(r'^[A-Za-z][A-Za-z0-9]*$', etok):
                fail('expected function name but got %s' % etok)
            return etok

        def unescape(str_lit):
            """ r'foo\bar' -> 'foo\bar' """
            try:
                return str_lit[1:-1].decode('string_escape')
            except:
                fail('invalid string literal %s' % str_lit)

        expr, epos = parse_pipeline(epos)
        epos = skip_ignorable(epos)
        return expr, ''.join(etokens[epos:])
        
    pos = 0  # Index into tokens array indicating unconsumed portion.
    while pos < len(tokens):
        token = tokens[pos]
        if not token.strip():
            pos += 1
            continue
        if token.startswith('{{define'):
            pos = parse_define(pos)
        else:
            break

    if pos < len(tokens) and name is not None:
        pos = define(name, pos)

    if pos < len(tokens):
        fail(pos, 'unparsed content %s' % ''.join(tokens[pos:]))

    return env


def escape(env, name):
    """Renders the named template safe for evaluation."""
    assert name in env.templates
    # TODO
    return env
