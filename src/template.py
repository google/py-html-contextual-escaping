#!/usr/bin/python

"""
An implementation of enough of Go templates to enable testing.
"""

import cStringIO as StringIO
import escaping
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
        raise NotImplementedError('abstract')

    def clone(self):
        """A structural copy"""
        return self.with_children([child.clone() for child in self.children()])

    def children(self):
        """Returns a tuple of the child nodes."""
        raise NotImplementedError('abstract')

    def with_children(self, children):
        """
        Returns a copy of this but with the given children.
        """
        raise NotImplementedError('abstract')

    def __str__(self):
        raise NotImplementedError('abstract')


class ExprNode(Node):
    """A node that is executed for its value"""
    def __init__(self, src, line):
        Node.__init__(self, src, line)


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

    def children(self):
        return ()

    def with_children(self, children):
        assert len(children) == 0
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

    def children(self):
        return (self.expr,)

    def with_children(self, children):
        assert(1 == len(children))
        return InterpolationNode(self.src, self.line, children[0])

    def __str__(self):
        return "{{%s}}" % self.expr


class ReferenceNode(ExprNode):
    """
    An expression node (a node that execute()s to a return value)
    whose value is determined soley by property lookups on the data value.
    """

    def __init__(self, src, line, properties):
        ExprNode.__init__(self, src, line)
        self.properties = tuple(properties)

    def execute(self, env, out):
        data = env.data
        for prop in self.properties:
            if data is None:
                break
            data = data.get(prop)
        return data

    def children(self):
        return ()

    def with_children(self, children):
        assert len(children) == 0
        return ReferenceNode(self.src, self.line, self.properties)

    def __str__(self):
        return ".%s" % '.'.join(self.properties)


class CallNode(ExprNode):
    """An function call"""

    def __init__(self, src, line, name, args):
        ExprNode.__init__(self, src, line)
        self.name = name
        self.args = tuple(args)

    def execute(self, env, out):
        return env.fns[self.name](
            *[arg.execute(env, out) for arg in self.args])

    def children(self):
        return self.args

    def with_children(self, children):
        return CallNode(self.src, self.line, self.name, children)

    def __str__(self):
        if len(self.args) == 1:
            return "%s | %s" % (str(self.args[0]), self.name)
        else:
            return '%s(%s)' % (
                self.name, ", ".join([str(arg) for arg in self.args]))


class StrLitNode(ExprNode):
    """A string literal in an expression"""

    def __init__(self, src, line, value):
        ExprNode.__init__(self, src, line)
        if type(value) not in (str, unicode):
            value = str(value)
        self.value = value

    def execute(self, env, out):
        return self.value

    def children(self):
        return ()

    def with_children(self, children):
        assert len(children) == 0
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

    def children(self):
        if self.expr:
            return (self.name, self.expr)
        return (self.name,)

    def with_children(self, children):
        assert len(children) <= 2
        name = children[0]
        expr = None
        if len(children) == 2:
            expr = children[1]
        return TemplateNode(self.src, self.line, name, expr)

    def __str__(self):
        expr = self.expr
        expr_str = ""
        if expr:
            expr_str = " %s" % self.expr
        return "{{template %s%s}}" % (self.name, expr_str)

class BlockNode(Node):
    """
    An abstract statement node that has an expression, a body, and an optional
    else clause.
    """

    def __init__(self, src, line, node_type, expr, body, else_clause):
        """
        node_type - the node type.  'if' for {{if}}...{{else}}...{{end}}.
        """
        Node.__init__(self, src, line)
        self.node_type = node_type
        self.expr = expr
        self.body = body
        self.else_clause = else_clause

    def children(self):
        if self.else_clause:
            return (self.expr, self.body, self.else_clause)
        return (self.expr, self.body)

    def with_children(self, children):
        expr = children[0]
        body = children[1]
        else_clause = None
        if len(children) > 2:
            assert len(children) == 3
            else_clause = children[2]
        return type(self)(self.src, self.line, expr, body, else_clause)

    def __str__(self):
        else_clause = self.else_clause
        if else_clause:
            return "{{%s %s}}%s{{else}}%s{{end}}" % (
                self.node_type, self.expr, self.body, else_clause)
        return "{{%s %s}}%s{{end}}" % (self.node_type, self.expr, self.body)


class WithNode(BlockNode):
    """Executes body in a more specific data context."""

    def __init__(self, src, line, expr, body, else_clause):
        BlockNode.__init__(self, src, line, 'with', expr, body, else_clause)

    def execute(self, env, out):
        data = self.expr.execute(env, None)
        if data:
            self.body.execute(env.with_data(data), out)
        elif self.else_clause:
            self.else_clause.execute(env, out)


class IfNode(BlockNode):
    """Conditional."""

    def __init__(self, src, line, expr, body, else_clause):
        BlockNode.__init__(self, src, line, 'if', expr, body, else_clause)

    def execute(self, env, out):
        if self.expr.execute(env, None):
            self.body.execute(env, out)
        elif self.else_clause:
            self.else_clause.execute(env, out)


class RangeNode(BlockNode):
    """Loop."""

    def __init__(self, src, line, expr, body, else_clause):
        BlockNode.__init__(self, src, line, 'range', expr, body, else_clause)

    def execute(self, env, out):
        iterable = self.expr.execute(env, None)
        if iterable:
            for value in iterable:
                self.body.execute(env.with_data(value), out)
        elif self.else_clause:
            self.else_clause.execute(env, out)


class ListNode(Node):
    """The concatenation of a series of nodes."""

    def __init__(self, src, line, elements):
        Node.__init__(self, src, line)
        self.elements = tuple(elements)

    def execute(self, env, out):
        for child in self.elements:
            child.execute(env, out)

    def children(self):
        return self.elements

    def with_children(self, children):
        return ListNode(self.src, self.line, children)

    def __str__(self):
        return ''.join([str(child) for child in self.elements])


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
        r'|\x27(?:[^\\\x27]|\\.)*\x27'
        r')*\}\})', code)

    # For each token, the line on which it appears.
    lines = []
    line = 0
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
    # template grammar which updated env.templates in place.
    # Functions take an index into the token stream and most return an
    # index to the token after the last they consumed.
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
        expr = _parse_expr(src, lines[pos], token[len('{{define'):-2])
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
        line = lines[pos]
        token = tokens[pos]
        match = re.search(
            r'^\{\{(?:(if|range|with|template|end|else)\b)?(.*)\}\}$', token)
        if not match:
            return TextNode(src, line, token), pos+1
        name = match.group(1)
        if not name:
            return InterpolationNode(
                src, line, _parse_expr(src, line, token[2:-2])), pos+1
        if name in ('end', 'else'):
            return None, pos
        if name == 'template':
            name_and_data = match.group(2)
            template_name, name_and_data = _parse_expr(
                src, line, name_and_data, consume_all=False)
            expr = None
            if name_and_data.strip():
                # TODO: wrong line number if there are linebreaks in the name
                # portion.
                expr = _parse_expr(src, line, name_and_data)
            return TemplateNode(src, line, template_name, expr), pos+1
        return parse_block(name, pos, _parse_expr(src, line, match.group(2)))

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


def _parse_expr(src, line, expr_text, consume_all=True):
    """
    Parse an expression from the front of the given text.

    If consume_all is true (the default), then the expression must
    be the only thing in expr_text, and only the expression is returned.

    Otherwise, the expression and the unparsed portion of expr_text are
    returned as a tuple.
    """

    line_ref = [line]
    etokens = re.findall(
        (r'[^\t\n\r \x27\x22()\|,]+'  # A run of non-breaking characters.
         r'|[\t\n\r ]+'  # Whitespace
         r'|[()\|,]'  # Punctuation
         # Below we make sure that we parse all possible sequences starting
         # with a quote character so that quotes are not silently dropped,
         # and check well-formedness below.
         r'|\x27(?:[^\\\x27\n\r]|\\[\n\r])*\x27?'  # '...'
         r'|\x22(?:[^\\\x22\n\r]|\\[\n\r])*\x22?'),  # "..."
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
        if etokens[epos] != token:
            fail('Expected %s, got %s' % (token, etokens[epos]))
        return epos + 1

    # There are two precedence levels.
    # highest - string literals, references, calls
    # lowest  - pipelines
    epos = 0

    def parse_pipeline(epos):
        expr, epos = parse_atom(epos)
        epos = skip_ignorable(epos)
        while epos < len(etokens) and etokens[epos] == '|':
            right, epos = parse_name(epos+1)
            expr = CallNode(src, expr.line, right, (expr,))
            epos = skip_ignorable(epos)  # Consume name and space.
        return expr, epos

    def parse_atom(epos):
        epos = skip_ignorable(epos)
        if epos == len(etokens):
            fail('missing expression part at end of %s' % expr_text)
        etoken = etokens[epos]
        ch0 = etoken[0]
        if ch0 == '.':  # Reference
            if etoken != '.':
                # .Foo.Bar -> ['Foo', 'Bar'] so we can lookup data elements
                # in order.
                parts = etoken[1:].split('.')
            else:
                # . means all data, so use () because following zero key
                # traversals leaves from data leaves us in the right place.
                parts = ()
            return ReferenceNode(src, line_ref[0], parts), epos+1
        if ch0 in ('"', "'"):
            if len(etoken) < 2 or etoken[-1] != ch0:
                fail('malformed string literal %s' % etoken)
            return (StrLitNode(src, line_ref[0], unescape(etoken)),
                    epos+1)
        # Assume a function call.
        line = line_ref[0]
        name, epos = parse_name(epos)
        epos = skip_ignorable(epos)
        epos = expect(epos, '(')
        epos = skip_ignorable(epos)
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
        Returns the value of the identifier token at etokens[epos] and
        the position after the identifier or fails with a useful
        error message.
        """
        epos = skip_ignorable(epos)
        if epos == len(etokens):
            fail('missing function name at end of %s' % expr_text)
        etok = etokens[epos]
        if not re.search(r'^[A-Za-z][A-Za-z0-9]*$', etok):
            fail('expected function name but got %s' % etok)
        return etok, epos+1

    def unescape(str_lit):
        """ r'foo\bar' -> 'foo\bar' """
        try:
            # See http://docs.python.org/library/codecs.html
            return str_lit[1:-1].decode('string_escape')
        except ValueError:
            fail('invalid string literal %s' % str_lit)

    expr, epos = parse_pipeline(epos)
    epos = skip_ignorable(epos)
    remainder = ''.join(etokens[epos:])
    if consume_all:
        if remainder:
            fail('Trailing content in expression: %s^%s'
                 % (expr_text[:-len(remainder)], remainder))
        return expr
    return expr, remainder


def escape(env, name):
    """
    Renders the named template safe for evaluation.

    This assumes env.templates[name] starts in an HTML text context.
    """
    assert name in env.templates
    env.fns['html'] = escaping.escape_html

    def esc(node):
        if isinstance(node, InterpolationNode):
            pipeline = Pipeline(node.expr)
            ensure_pipeline_contains(pipeline, ('html',))
            return node.with_children((pipeline.expr,))
        elif isinstance(node, ExprNode):
            return node
        return node.with_children([esc(child) for child in node.children()])

    env.templates[name] = esc(env.templates[name])

    return env


class Pipeline(object):
    """
    A wrapper that allows convenient manipulation of chained function calls.
    """

    def __init__(self, expr):
        self.expr = expr

    def element_at(self, index):
        """
        A function that takes an index and returns the name of the
        pipeline element at that index or None if out of bounds.

        When .|a|b is b(a(.)), element_at(0) is 'a', and element_at(1) is 'b'.
        """
        result = [None]
        def walk(expr):
            if not _is_pipe(expr):
                return 0
            arg_index = walk(expr.args[0])
            if arg_index == index:
                result[0] = expr.name
            return arg_index+1
        walk(self.expr)
        return result[0]

    def insert_element_at(self, index, name):
        """
        takes an index and a pipeline element to insert.
        After this call, element_at(index) == name.

        When .|a|b|c is c(b(a(.)))
        # insert_element_at(1, foo) should produce
        # .|a|foo|b which is c(b(foo(a(.))))
        """
        def walk(expr):
            if not _is_pipe(expr):
                return 0, expr
            arg = expr.args[0]
            arg_index, new_arg = walk(arg)
            if arg_index == index:
                new_arg = CallNode(new_arg.src, new_arg.line, name, (new_arg,))
            if arg is not new_arg:
                expr = expr.with_children((new_arg,))
            return arg_index+1, expr
        arg_index, expr = walk(self.expr)
        if arg_index == index:  # Insertion at end.
            expr = CallNode(expr.src, expr.line, name, (expr,))
        self.expr = expr


def ensure_pipeline_contains(pipeline, to_insert):
    '''
    ensures that an interpolated expression has calls to the functions named
    in to_insert in order.
    If the pipeline already has some of the named functions, do not interfere.
    For example, if pipeline is (.X | html) and to_insert is
    ["escape_js_val", "html"] then it
    has one matching, "html", and one to insert, "escape_js_val", to produce
    (.X | escapeJSVal | html).

    pipeline - an object that supports element_at and insert_element_at methods
               with the same semantics as Pipeline.
    to_insert - the elements that the pipeline should contain in order.
    '''

    if not to_insert:
        return

    # Merge existing identifier commands with the sanitizers needed.
    el_pos = 0
    while True:
        element = pipeline.element_at(el_pos)
        if element is None:
            break
        for ti_pos in xrange(0, len(to_insert)):
            if _esc_fns_eq(element, to_insert[ti_pos]):
                for name in to_insert[:ti_pos]:
                    pipeline.insert_element_at(el_pos, name)
                    el_pos += 1
                to_insert = to_insert[ti_pos+1:]
                break
        el_pos += 1
    # Insert any remaining at the end.
    for name in to_insert:
        pipeline.insert_element_at(el_pos, name)
        el_pos += 1


def _esc_fns_eq(fn_name_a, fn_name_b):
    """
    Tests whether two escaping function names do the same work.
    """
    return fn_name_a == fn_name_b


def _is_pipe(expr):
    """
    True if expr is a call with a single argument.

    Since template syntax allows f(x) to be written x | f, single argument
    functions are called pipeline elements.
    """
    return isinstance(expr, CallNode) and len(expr.args) == 1
