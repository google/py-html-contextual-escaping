#!/usr/bin/env python -O

"""
An implementation of enough of Go templates to allow testing of auto-escaping.

Usage:
    # Parse templates.
    env = parse_templates(Loc('/my/template/file'), file_content)
    # Execute the templates with some data.
    template_output = env.with_data({ 'foo': 'bar' }).sexecute()
   
Template definitions contain embedded commands surrounded in {{...}}.
  {{define 'name'}}...{{end}}
      defines a template
  {{if expr}}...{{else}}...{{end}}
      a conditional
  {{range expr}}...{{else}}}...{{end}}
      loops over a series executing the body with the value as the data context.
      If the series is falsey/empty executes the optional {{else}} part instead.
  {{with expr}}...{{else}}...{{end}}
      executes the body using expr as the data context.
      If expr is falsey, executes the optional {{else}} part instead.
  {{expr}}
      emits the result of expr as output
  {{template 'name' expr}}
      executed the named template.  If the optional expr is present, uses that
      as the data context for the template instead of the current data context.

Template expressions can have the form:
  Literal values: 42, -1.5, 'foo', True, False, null
  Function calls: foo(expr, expr)
  Pipes:          expr | foo

The pipe syntax (foo | bar) is merely syntactic sugar for a call: bar(foo)

The set of functions is determined by the environment.  Env().fns is a dict
mapping function names to the python functions that implement them.
"""

import cStringIO as StringIO
import collections
import escaping
import re

# Functions available by default.
_BUILTIN_FNS = {
    'noescape': lambda x: x,
    }
for _builtin_fn in escaping.SANITIZER_FOR_ESC_MODE:
    if _builtin_fn is not None:
        _BUILTIN_FNS[_builtin_fn.__name__] = _builtin_fn


class Env(object):
    """Templates and the environment in which they can be executed."""

    def __init__(self, data=None, fns=None, templates=None):
        self.data = data
        self.fns = fns or _BUILTIN_FNS
        self.templates = templates or {}

    def with_data(self, data):
        """
        Returns an environment with the same functions and templates but
        with the given data value.
        """
        return Env(data=data, fns=self.fns, templates=self.templates)

    def with_fns(self, fns):
        """
        Returns an environment with the same templates and data value but
        with the given function map in addition.
        """
        all_fns = dict(self.fns)
        for name in fns:
            assert type(name) in (str, unicode), name
            fun = fns[name]
            assert isinstance(fun, collections.Callable), name
            all_fns[name] = fun
        return Env(self.data, all_fns, self.templates)

    def execute(self, name, out):
        """
        Executes the named template in this environment appending
        its output to out.
        """
        self.templates[name].execute(self, out)

    def sexecute(self, name):
        """Returns the result of executing the named template as a string."""
        buf = StringIO.StringIO()
        self.execute(name, buf)
        return buf.getvalue()

    def __str__(self):
        """Returns a form parseable by parse_templates."""
        names = self.templates.keys()
        names.sort()
        return '\n\n'.join(
            [("{{define %r}}%s{{end}}" % (name, self.templates[name]))
             for name in names])

    def parse_templates(self, loc, code, name=None):
        """
        Augments this with template definitions parsed from code.
        See module function parse_templates for description of parameters.

        For example,
            env.parse_templates(loc, '{{define "foo"}}Hello{{end}}World', 'bar')
        will augment env with two templates so that
            env.sexecute('foo') == 'Hello' and env.sexecute('bar') == 'World'
        """
        _parse_templates_into(self.templates, loc=loc, code=code, name=name)


class Loc(object):
    """Describes a location within a source code file."""

    def __init__(self, src, line=1):
        """
        src - description of source of code.  For example a path or URL.
        line - 1 greater than the number of line breaks preceding the location.
        """
        self.src = src
        self.line = line

    def __str__(self):
        return '%s:%s' % (self.src, self.line)


class Node(object):
    """Abstract base class for a tree-interpreted template."""

    def __init__(self, loc):
        self.loc = loc

    def execute(self, env, out):
        """Appends output to out, or returns the result if an expression."""
        raise NotImplementedError('abstract')  # pragma: no cover

    def clone(self):
        """Returns a structural copy."""
        return self.with_children([child.clone() for child in self.children()])

    def children(self):
        """Returns a tuple of the child nodes."""
        raise NotImplementedError('abstract')  # pragma: no cover

    def with_children(self, children):
        """Returns a copy of this but with the given children."""
        raise NotImplementedError('abstract')  # pragma: no cover

    def reduce_traces(self, start_state, analyzer):
        """
        Implements the algorithm described in module trace_analysis.

        analyzer - obeys the contract for trace_analysis.Analyzer
        """
        raise NotImplementedError('abstract')  # pragma: no cover

    def __str__(self):
        raise NotImplementedError('abstract')  # pragma: no cover


class ExprNode(Node):
    """Abstract base class for a node that is executed for its value."""

    def __init__(self, loc):
        Node.__init__(self, loc)

    def evaluate(self, env):
        """Returns the result of evaluating the expression in env."""
        raise NotImplementedError('abstract')  # pragma: no cover

    def execute(self, env, out):
        return self.execute(env, None)

    def reduce_traces(self, start_state, analyzer):
        # Trace analysis should not descend into expressions.
        raise AssertionError()  # pragma: no cover


class _TextNode(Node):
    """
    A chunk of raw text in the template's output language that was supplied
    by a template author and so not controllable by an attacker.
    """

    def __init__(self, loc, text):
        Node.__init__(self, loc)
        assert type(text) in (str, unicode)
        self.text = text

    def execute(self, env, out):
        out.write(self.text)

    def children(self):
        return ()

    def with_children(self, children):
        assert len(children) == 0
        return _TextNode(self.loc, self.text)

    def to_raw_content(self):
        """
        Returns the node's text to satisfy the step value definition used by
        the trace analyzer.
        """
        return self.text

    def with_raw_content(self, new_content):
        """Returns a version of this node but with the given text content."""
        return _TextNode(self.loc, new_content)

    def reduce_traces(self, start_state, analyzer):
        return analyzer.step(start_state, self, debug_hint=self.loc)

    def __str__(self):
        return self.text


class _InterpolationNode(Node):
    """An interpolation of an untrusted expression into the template output."""

    def __init__(self, loc, expr):
        Node.__init__(self, loc)
        assert isinstance(expr, ExprNode)
        self.expr = expr

    def execute(self, env, out):
        value = self.expr.evaluate(env)
        if value is not None:
            if type(value) not in (str, unicode):
                value = str(value)
            out.write(value)

    def children(self):
        return (self.expr,)

    def with_children(self, children):
        assert(1 == len(children))
        return _InterpolationNode(self.loc, children[0])

    def to_pipeline(self):
        """Satisfies the step value definition used by the trace analyzer."""
        return Pipeline(self.expr)

    def with_pipeline(self, pipeline):
        """Satisfies the step value modifier used by the trace analyzer."""
        return _InterpolationNode(self.loc, pipeline.expr)

    def reduce_traces(self, start_state, analyzer):
        return analyzer.step(
            start_state, self, debug_hint='%s: %s' % (self.loc, self))

    def __str__(self):
        return "{{%s}}" % self.expr


class _ReferenceNode(ExprNode):
    """
    An expression node (a node that execute()s to a return value)
    whose value is determined soley by property lookups on the data value.
    """

    def __init__(self, loc, properties):
        ExprNode.__init__(self, loc)
        self.properties = tuple(properties)

    def evaluate(self, env):
        data = env.data
        for prop in self.properties:
            if not hasattr(data, 'get'):
                return None
            data = data.get(prop)
        return data

    def children(self):
        return ()

    def with_children(self, children):
        assert len(children) == 0
        return _ReferenceNode(self.loc, self.properties)

    def __str__(self):
        return ".%s" % '.'.join(self.properties)


class _CallNode(ExprNode):
    """An function call"""

    def __init__(self, loc, name, args):
        ExprNode.__init__(self, loc)
        self.name = name
        self.args = tuple(args)

    def evaluate(self, env):
        return env.fns[self.name](
            *[arg.evaluate(env) for arg in self.args])

    def children(self):
        return self.args

    def with_children(self, children):
        return _CallNode(self.loc, self.name, children)

    def __str__(self):
        if len(self.args) == 1:
            return "%s | %s" % (str(self.args[0]), self.name)
        else:
            return '%s(%s)' % (
                self.name, ", ".join([str(arg) for arg in self.args]))


class _LiteralNode(ExprNode):
    """A literal value."""

    def __init__(self, loc, value):
        ExprNode.__init__(self, loc)
        assert type(value) in (str, unicode, bool, int, long, float)
        self.value = value

    def evaluate(self, env):
        return self.value

    def children(self):
        return ()

    def with_children(self, children):
        assert len(children) == 0
        return _LiteralNode(self.loc, self.value)

    def __str__(self):
        return repr(self.value)


class _TemplateNode(Node):
    """A call to another template."""

    def __init__(self, loc, name, expr):
        Node.__init__(self, loc)
        self.name = name
        self.expr = expr

    def execute(self, env, out):
        name = self.name.evaluate(env)
        if self.expr:
            env = env.with_data(self.expr.evaluate(env))
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
        return _TemplateNode(self.loc, name, expr)

    def to_callee(self):
        """
        Satisfies the step value definition used by the trace analyzer.

        Returns the template name.
        """
        # TODO: Enumerate possible values or error out if unanalyzable.
        return self.name.evaluate(None)

    def with_callee(self, callee):
        """
        Satisfies the step value definition used by the trace analyzer.

        Returns a call to the named template with the same data as this call.
        """
        assert type(callee) is str
        return _TemplateNode(
            self.loc, _LiteralNode(self.name.loc, callee), self.expr)

    def reduce_traces(self, start_state, analyzer):
        return analyzer.step(start_state, self, debug_hint=self.loc)

    def __str__(self):
        expr = self.expr
        expr_str = ""
        if expr:
            expr_str = " %s" % self.expr
        return "{{template %s%s}}" % (self.name, expr_str)


class _BlockNode(Node):
    """
    An abstract statement node that has an expression, a body, and an optional
    else clause.
    """

    def __init__(self, loc, expr, body, else_clause):
        Node.__init__(self, loc)
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
        return type(self)(self.loc, expr, body, else_clause)

    def block_type(self):
        """
        'if' for {{if}}...{{else}}...{{end}}.
        """
        raise NotImplementedError('abstract')  # pragma: no cover

    def __str__(self):
        else_clause = self.else_clause
        if else_clause:
            return "{{%s %s}}%s{{else}}%s{{end}}" % (
                self.block_type(), self.expr, self.body, else_clause)
        return "{{%s %s}}%s{{end}}" % (self.block_type(), self.expr, self.body)


class _WithNode(_BlockNode):
    """Executes body in a more specific data context."""

    def __init__(self, loc, expr, body, else_clause):
        _BlockNode.__init__(self, loc, expr, body, else_clause)

    def execute(self, env, out):
        data = self.expr.evaluate(env)
        if data:
            self.body.execute(env.with_data(data), out)
        elif self.else_clause:
            self.else_clause.execute(env, out)

    def block_type(self):
        return 'with'

    def reduce_traces(self, start_state, analyzer):
        with_end = self.body.reduce_traces(start_state, analyzer)
        else_end = start_state
        if self.else_clause:
            else_end = self.else_clause.reduce_traces(start_state, analyzer)
        return analyzer.join(
            (with_end, else_end),
            debug_hint='%s: {{%s}}' % (self.loc, self.block_type()))


class _IfNode(_BlockNode):
    """Conditional."""

    def __init__(self, loc, expr, body, else_clause):
        _BlockNode.__init__(self, loc, expr, body, else_clause)

    def execute(self, env, out):
        if self.expr.evaluate(env):
            self.body.execute(env, out)
        elif self.else_clause:
            self.else_clause.execute(env, out)

    def block_type(self):
        return 'if'

    def reduce_traces(self, start_state, analyzer):
        then_end = self.body.reduce_traces(start_state, analyzer)
        else_end = start_state
        if self.else_clause:
            else_end = self.else_clause.reduce_traces(start_state, analyzer)
        return analyzer.join(
            (then_end, else_end),
            debug_hint='%s: {{%s}}' % (self.loc, self.block_type()))


class _RangeNode(_BlockNode):
    """Loop."""

    def __init__(self, loc, expr, body, else_clause):
        _BlockNode.__init__(self, loc, expr, body, else_clause)

    def execute(self, env, out):
        iterable = self.expr.evaluate(env)
        if iterable:
            for value in iterable:
                self.body.execute(env.with_data(value), out)
        elif self.else_clause:
            self.else_clause.execute(env, out)

    def block_type(self):
        return 'range'

    def reduce_traces(self, start_state, analyzer):
        zero_end = start_state
        if self.else_clause:
            zero_end = self.else_clause.reduce_traces(start_state, analyzer)
        once_end = self.body.reduce_traces(start_state, analyzer)
        twice_end = self.body.reduce_traces(once_end, analyzer)
        if once_end != twice_end:
            return analyzer.no_steady_state(
                (once_end, twice_end),
                debug_hint='%s: {{%s}}' % (self.loc, self.block_type()))
        return analyzer.join(
            (zero_end, once_end),
            debug_hint='%s: {{%s}}' % (self.loc, self.block_type()))


class _ListNode(Node):
    """The concatenation of a series of nodes."""

    def __init__(self, loc, elements):
        Node.__init__(self, loc)
        self.elements = tuple(elements)

    def execute(self, env, out):
        for child in self.elements:
            child.execute(env, out)

    def children(self):
        return self.elements

    def with_children(self, children):
        return _ListNode(self.loc, children)

    def reduce_traces(self, start_state, analyzer):
        for element in self.elements:
            start_state = element.reduce_traces(start_state, analyzer)
        return start_state

    def __str__(self):
        return ''.join([str(child) for child in self.elements])


def parse_templates(loc, code, name=None):
    """
    Parses a template definition or set of template definitions.

    This is the dual of env.__str__.

    loc - The source code location at the start of code.
    code - Zero or more {{define}}...{{end}} and optionally zero or more
           statements at the end which will be treated as the body of the
           template named name.
    name - The name to use for the implied template definition.

    For example,
        parse_templates(..., '{{define "foo"}}Hello{{end}}World!', name='bar')
    will return an environment, env, with two templates so that
        env.sexecute('foo') == 'Hello'
        env.sexecute('bar') == 'World!'

    Returns an Env containing the builtin function definitions and
    the parsed templates.
    """

    env = Env(None, dict(_BUILTIN_FNS), {})
    _parse_templates_into(env.templates, loc, code, name)
    return env

def _parse_templates_into(name_to_body, loc, code, name=None):
    """
    Parses a template definition or set of template definitions
    into an existing environment.
    """

    assert type(code) in (str, unicode)
    assert name is None or type(name) in (str, unicode)

    # Normalize newlines.
    code = re.sub(r'\r\n?', '\n', code)

    # White-space at the end is ignorable.
    # Code below ignores white-space at the start.
    code = code.rstrip()

    # Split src into a run of non-{{...}} tokens with
    # {{...}} constructs in-between.
    # Inside a {{...}}, '}}' can appear inside a quoted string but not
    # elsewhere.  Quoted strings are \-escaped.
    toks = _Tokens(
        loc,
        [tok for tok in  # Avoid blank text nodes.
         re.split(
             r'(\{\{(?:'
             r'[^\x22\x27\}]'
             r'|\x22(?:[^\\\x22\n\r]|\\[^\n\r])*\x22?'
             r'|\x27(?:[^\\\x27\n\r]|\\[^\n\r])*\x27?'
             r')*\}\})', code)
         if tok])


    # The inner functions below comprise a recursive descent parser for the
    # template grammar which updates name_to_body in place.
    # Functions consume tokens so all operate on the queue defined above.
    def parse_define():
        """Parses a {{{define 'name'}}}...{{end}} and updates name_to_body."""
        token = toks.peek()
        if token is None or not re.search(
            r'(?s)\A\{\{define\b.*\}\}\Z', token):
            toks.fail('expected {{define...}} not %s' % token)
        name_expr = _parse_expr(
            toks.loc_at(), token[len('{{define'):-2].strip())
        name = name_expr.evaluate(None)
        if type(name) not in (str, unicode):
            toks.fail('expected quoted template name, not %s' % name_expr)
        toks.consume()
        define(name)
        toks.expect('{{end}}')

    def define(name):
        """Updates name_to_body[name] or fails with an informative error"""
        if name in name_to_body:
            toks.fail('redefinition of %r' % name)
        name_to_body[name] = parse_list()

    def parse_list():
        """Parses a series of statement nodes."""
        loc = toks.loc_at()
        children = []
        while True:
            atom = parse_atom()
            if atom is None:
                break
            children.append(atom)
        if len(children) == 1:
            return children[0]
        return _ListNode(loc, children)

    def parse_atom():
        """Parses a single full statement node."""
        token = toks.peek()
        if token is None:
            return None
        loc = toks.loc_at()
        match = re.search(
            r'\A\{\{(?:(if|range|with|template|end|else)\b)?(.*)\}\}\Z', token)
        if not match:
            toks.consume()
            return _TextNode(loc, token)
        name = match.group(1)
        if name in ('else', 'end'):
            return None
        toks.consume()
        if not name:
            return _InterpolationNode(loc, _parse_expr(loc, token[2:-2]))
        if name == 'template':
            name_and_data = match.group(2)
            template_name, name_and_data = _parse_expr(
                loc, name_and_data, consume_all=False)
            expr = None
            if not name_and_data.is_empty():
                # Loc is now irrelevant since name_and_data is a token queue,
                # so even if there are line-breaks in name, the error messages
                # from parsing data will point to the right line.
                expr = _parse_expr(loc, name_and_data)
            return _TemplateNode(loc, template_name, expr)
        return parse_block(loc, name, _parse_expr(loc, match.group(2)))

    def parse_block(loc, name, expr):
        """Parses a _BlockNode, like {{if}}, {{with}}, etc."""
        body = parse_list()
        else_clause = None
        if toks.check('{{else}}'):
            else_clause = parse_list()
        toks.expect('{{end}}')
        if name == 'if':
            ctor = _IfNode
        elif name == 'range':
            ctor = _RangeNode
        else:
            assert name == 'with'
            ctor = _WithNode
        return ctor(loc, expr, body, else_clause)

    while not toks.is_empty():
        token = toks.peek()
        if not token.strip():
            toks.consume()
            continue
        if token.startswith('{{define'):
            parse_define()
        else:
            # A source file is zero or more {{define}}s
            # optionally followed by zero or more statements that make up
            # the body of the template with the given name.
            # Fall through to parse the optional template body below.
            if name is not None:
                define(name)
            if not toks.is_empty():
                toks.fail('unparsed content %s' % toks)

    # The empty input should translate to a named template with an empty body.
    if name is not None and name not in name_to_body:
        define(name)


def _parse_expr(loc, toks, consume_all=True):
    """
    Parse an expression from the front of the given text.

    If consume_all is true (the default), then the expression must
    be the only thing in expr_text, and only the expression is returned.

    Otherwise, the expression and the unparsed portion of expr_text are
    returned as a tuple.
    """

    if type(toks) in (str, unicode):
        toks = _ExprTokens(
            loc,
            re.findall(
                (r'[^\t\n\r \x27\x22()\|,]+'  # Non-breaking characters.
                 r'|[\t\n\r ]+'  # Whitespace
                 r'|[()\|,]'  # Punctuation
                 # We parse all possible sequences starting with a quote so
                 # that quotes are not silently dropped, and enforce string
                 # well-formedness later.
                 r'|\x27(?:[^\\\x27\n\r]|\\[^\n\r])*\x27?'  # '...'
                 r'|\x22(?:[^\\\x22\n\r]|\\[^\n\r])*\x22?'),  # "..."
                toks))
    assert isinstance(toks, _ExprTokens)
    assert type(consume_all) is bool

    all_toks = _ExprTokens(toks.loc, toks.tokens)

    # There are two precedence levels.
    # highest - string literals, references, calls
    # lowest  - pipelines

    def parse_pipeline():
        """
        Parses the lowest precedence production (atom '|' atom '|' | ...).
        """
        expr = parse_atom()
        while toks.check('|'):
            expr = _CallNode(expr.loc, parse_name(), (expr,))
        return expr

    def parse_atom():
        """
        Parses function calls, literals, and references which do not nest
        except inside parentheses so which are all equally high precedence.
        """
        toks.skip_ignorable()
        token = toks.peek()
        if token is None:
            toks.fail('missing expression part at end of %s'
                      % (str(all_toks) or 'input'))
        loc = toks.loc_at()
        ch0 = token[0]
        if ch0 == '.':  # Reference
            # .Foo.Bar -> ['Foo', 'Bar'] so we can lookup data elements
            # in order.
            parts = tuple(token[1:].split('.'))
            if parts == ('',):
                # . means all data, so use () because following zero key
                # traversals leaves from data leaves us in the right place.
                parts = ()
            toks.consume()
            return _ReferenceNode(loc, parts)
        if ch0 in ('"', "'"):
            if len(token) < 2 or token[-1] != ch0:
                toks.fail('malformed string literal %s' % token)
            toks.consume()
            return _LiteralNode(loc, unescape(token))
        if _NUMBER.search(token):
            toks.consume()
            if _INT.search(token):
                number = int(token, 0)
            else:
                number = float(token)
            return _LiteralNode(loc, number)
        # Assume a function call or keyword value.
        name = parse_name()
        if name in _LITERAL_VALUES:
            return _LiteralNode(loc, _LITERAL_VALUES[name])
        toks.expect('(')
        args = []
        if not toks.check(')'):
            while True:
                args.append(parse_pipeline())
                if not toks.check(','):
                    break
            toks.expect(')')
        return _CallNode(loc, name, args)

    def parse_name():
        """
        Returns the value of the identifier token at etokens[epos] and
        the position after the identifier or fails with a useful
        error message.
        """
        toks.skip_ignorable()
        token = toks.peek()
        if token is None:
            toks.fail('missing function name at end of input')
        if not re.search(r'\A[A-Za-z][A-Za-z0-9_]*\Z', token):
            toks.fail('expected function name but got %s' % token)
        toks.consume()
        return token

    def unescape(str_lit):
        """ r'foo\bar' -> 'foo\bar' """
        try:
            # See http://docs.python.org/library/codecs.html
            return str_lit[1:-1].decode('string_escape')
        except ValueError:
            toks.fail('invalid string literal %s' % str_lit)

    expr = parse_pipeline()
    toks.skip_ignorable()
    if consume_all:
        if not toks.is_empty():
            remainder = str(toks)
            all_code = str(all_toks)
            toks.fail('trailing content in expression: %s^%s'
                      % (all_code[:-len(remainder)], remainder))
        return expr
    return expr, toks


class _Tokens(object):
    """A cursor over a sequence of tokens."""

    def __init__(self, loc, tokens):
        if type(loc) in (str, unicode):
            loc = Loc(loc)
        assert hasattr(loc, 'src') and hasattr(loc, 'line')
        self.loc = loc
        self.tokens = tuple(tokens)
        self.line = loc.line

    def is_empty(self):
        """True if there are uncomsumed tokens remaining."""
        return not self.tokens

    def is_ignorable(self):
        """
        True if the token at the front of the queue is ignorable.
        The default implementation returns False for non-empty tokens,
        but may be overridden.
        """
        return self.peek() == ''

    def skip_ignorable(self):
        """Consumes white-space tokens"""
        while not self.is_empty() and self.is_ignorable():
            self.consume()

    def loc_at(self):
        """The location of the token cursor."""
        return Loc(self.loc.src, self.line)

    def fail(self, msg):
        """
        Raises a parse exception including the location of the cursor.
        """
        raise ParseError('%s: %s' % (self.loc_at(), msg))

    def peek(self):
        """
        The token at the cursor or None if the cursor has reached the
        end of the input.
        """
        if not self.tokens:
            return None
        return self.tokens[0]

    def consume(self, n_tokens=1):
        """Advances the cursor past the current token."""
        line = self.line
        for consumed in self.tokens[:n_tokens]:
            pos = -1
            while True:
                pos = consumed.find('\n', pos+1)
                if pos < 0:
                    break
                line += 1
        self.line, self.tokens = line, self.tokens[n_tokens:]

    def check(self, token):
        """
        If the first unignorable token matches the given token,
        consumes it and returns True, otherwise returns False.
        """
        self.skip_ignorable()
        if self.peek() != token:
            return False
        self.consume()
        return True

    def expect(self, token):
        """
        Consume the first unignorable token if it matches token, otherwise
        fail with an error message.
        """
        if not self.check(token):
            if self.is_empty():
                self.fail('expected %s at end of input' % token)
            else:
                self.fail('expected %s, got %s' % (token, self.peek()))

    def __str__(self):
        """The text of the unconsumed tokens."""
        return ''.join(self.tokens)


class _ExprTokens(_Tokens):
    """A token queue suitable for parsing ExprNodes."""

    def __init__(self, loc, tokens):
        _Tokens.__init__(self, loc, tokens)

    def is_ignorable(self):
        token = self.peek()
        if token is not None and not token.strip():
            return True


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
            """Count back from the end of the pipeline to find the element."""
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
            """Count back from the end of the pipeline to find the element."""
            if not _is_pipe(expr):
                return 0, expr
            arg = expr.args[0]
            arg_index, new_arg = walk(arg)
            if arg_index == index:
                new_arg = _CallNode(new_arg.loc, name, (new_arg,))
            if arg is not new_arg:
                expr = expr.with_children((new_arg,))
            return arg_index+1, expr
        arg_index, expr = walk(self.expr)
        if arg_index == index:  # Insertion at end.
            expr = _CallNode(expr.loc, name, (expr,))
        self.expr = expr


def _is_pipe(expr):
    """
    True if expr is a call with a single argument.

    Since template syntax allows f(x) to be written x | f, single argument
    functions are called pipeline elements.
    """
    return isinstance(expr, _CallNode) and len(expr.args) == 1


_LITERAL_VALUES = {
    'None': None,
    'True': True,
    'False': False,
    }

_INT = re.compile('\A[+-]?(0[xX][0-9A-Fa-f]+|0+|[1-9][0-9]*)\Z')

_NUMBER = re.compile(
    '\A[+-]?('
    # Hex
    '0[xX][0-9A-Fa-f]+'
    # Decimal
    '|(?:'
      # Integer part and optional fraction
      '(?:0+|[1-9][0-9]*)(?:\.[0-9]*)?'
      # Decimal point and mandatory fraction
      '|\.[0-9]+'
    ')'
    # Optional exponent
    '(?:[eE][+-]?[0-9]+)?'
    ')\Z')


class ParseError(BaseException):
    """
    Raised on an invalid parser input.
    """

    def __init__(self, msg):
        BaseException.__init__(self, msg)
