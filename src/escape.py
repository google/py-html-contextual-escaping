#!/usr/bin/python

"""
Implements the HTML contextual escaping algorithm as defined at
http://js-quasis-libraries-and-repl.googlecode.com/svn/trunk/safetemplate.html
"""

import context
import context_update
import debug
import escaping
import trace_analysis


def escape(name_to_body, public_template_names, start_state=context.STATE_TEXT):
    """
    name_to_body - maps template names to template bodies.
        A template body is an object that implements
        1. reduce_traces(start_state, analyzer) -> end_state
        2. clone() -> a structural copy of the body that is distinct according
           to == and is also a template body.
        3. the body node interface described below.
    public_template_names - the names that might be called with an empty
        output buffer in the given start state.
    start_state - the state in which the named templates might be called.

    A body node is an object that implements
        1. children() -> a series of nodes
        2. with_children(children) -> produces a structural copy of
           the body but with the given children instead of children().
    step values must also be body nodes, and the transitively enumerated nodes
    of a body must include all step values encountered when following traces
    that do not include external calls.

    name_to_body may be augmented with new template definitions as a result of
    this call.

    If escape exits with an exception, then it is unsafe to use the templates
    in name_to_body.
    """
    analyzer = _Analyzer(name_to_body, start_state)

    has_errors = False

    for name in public_template_names:
        end_state = analyzer.external_call(name, start_state, None)
        if context.is_error_context(end_state):
            has_errors = True
        elif end_state != start_state:
            # Templates should start and end in the same context.
            # Otherwise concatenation of the output from safe templates is not
            # safe.
            analyzer.warn(
                'template %s does not end in the same context it starts' % name)
            has_errors = True

    if not has_errors:
        analyzer.rewrite()
    else:
        raise Exception('\n'.join(analyzer.warnings))


class _Analyzer(trace_analysis.Analyzer):
    """
    Applies the context_update algorithm to text nodes, builds
    side-tables of pipelines that need to be updated, and clones
    templates that are used in non-start contexts.
    """

    def __init__(self, name_to_body, start_state, templates=None):
        trace_analysis.Analyzer.__init__(self)
        # Maps template names to bodies.
        self.name_to_body = name_to_body
        # Maps (name, start_context) -> (body, end_context)
        self.start_state = start_state
        # Maps (template_name, start_context) pairs to end contexts
        self.templates = dict(templates or {})
        # Tracks the set of templates and the contexts in which they are
        # called.  A set (name, start_context)
        self.called = set()
        # Maps pipelines to escaping modes
        self.interps = {}
        # Maps external calls (step_values) to the contexts
        # in which they occur.
        # This assumes that cloned() step_values are distinct
        # from the original.
        self.calls = {}
        # Messages that explain failure to escape.
        self.warnings = []

    def warn(self, msg):
        """Queues a message explaining a problem noticed during escaping."""
        self.warnings.append(msg)

    def step(self, start_state, step_value, debug_hint=None):
        if hasattr(step_value, 'to_raw_content'):
            raw_content = step_value.to_raw_content()
            if raw_content is not None:
                end_state = context_update.process_raw_text(
                    raw_content, start_state)
                if (context.is_error_context(end_state)
                    and not context.is_error_context(start_state)):
                    self.warn('bad content in %s: `%s`' % (
                        debug.context_to_string(start_state), raw_content))
                return end_state
        if hasattr(step_value, 'to_pipeline'):
            pipeline = step_value.to_pipeline()
            if pipeline is not None:
                state, esc_modes = (
                    context_update.escaping_mode_for_hole(start_state))
                self.interps[step_value] = pipeline, esc_modes
                return state
        if hasattr(step_value, 'to_callee'):
            callee = step_value.to_callee()
            if callee is not None:
                end_ctx = self.external_call(callee, start_state, debug_hint)
                self.calls[step_value] = start_state
                return end_ctx
        return start_state

    def join(self, states, debug_hint=None):
        return reduce(context_update.context_union, states)

    def external_call(self, tmpl_name, start_ctx, debug_hint=None):
        """
        Makes sure that the named template can be called in the given context
        and returns the context after a successful call to the template in the
        start context.
        """
        key = (tmpl_name, start_ctx)
        self.called.add(key)
        if key in self.name_to_body:
            end_context = self.name_to_body[key]
            return end_context
        body = self.name_to_body.get(tmpl_name)
        if body is None:
            self.warn('%sNo such template %s' % (debug_hint or '', tmpl_name))
            return context.STATE_ERROR
        if start_ctx != self.start_state:
            # Derive a copy so that calls and pipelines can be written
            # independently of the original.
            body = body.clone()
        return self._compute_end_context(
            start_ctx, tmpl_name, body, debug_hint)

    def no_steady_state(self, states, debug_hint=None):
        self.warn('%sloop oscillates between states (%s)' % (
            debug_hint or '',
            ', '.join([debug.context_to_string(state) for state in states])))
        return context.STATE_ERROR

    def _compute_end_context(self, start_ctx, tmpl_name, body, debug_hint):
        """Propagate context over the body."""
        ctx, problems = self._escape_template_body(tmpl_name, start_ctx, body)
        if problems is not None:
            # Look for a fixed point by assuming c1 as the output context.
            ctx2, problems2 = self._escape_template_body(tmpl_name, ctx, body)
            if problems2 is None:
                ctx, problems = ctx2, None
        if problems is not None:
            if not context.is_error_context(ctx):
                # We have not explained the problem yet.
                self.warn(
                    "%scannot compute output context for template %s in %s" % (
                        debug_hint or '', tmpl_name,
                        debug.context_to_string(start_ctx)))
            self.warnings.extend(problems)
            return context.STATE_ERROR
        return ctx

    def _escape_template_body(self, tmpl_name, ctx, body):
        """
        escapes the given template assuming the given output context.

        It returns the best guess at an output context, and any problems
        encountered along the way or None on success.
        """
        key = (tmpl_name, ctx)
        # We need to assume an output context so that recursive template calls
        # take the fast path out of escapeTree instead of infinitely recursing.
        # Naively assuming that the input context is the same as the output
        # works >90% of the time.
        self.templates[key] = (body, ctx)

        # Derive an analyzer so we can see if our assumptions hold before
        # committing to them.
        analyzer = _Analyzer(self.name_to_body, self.start_state,
                             templates=self.templates)
        end_ctx = body.reduce_traces(ctx, analyzer)

        # Do not update self if we cannot confidently compute an end context.
        if (context.is_error_context(end_ctx)
            # If the template is recursively called, end_ctx must be
            # consistent with our assumption.  Otherwise our assumption
            # didn't factor into the computation of end_ctx, so we can
            # just use end_ctx.
            or (key in self.called and ctx != end_ctx)):
            self.templates[key] = (body, context.STATE_ERROR)
            return end_ctx, analyzer.warnings

        # Copy inferences and pending changes from analyzer back into self.
        _copyinto(self.templates, analyzer.templates)
        _copyinto(self.called, analyzer.called)
        _copyinto(self.interps, analyzer.interps)
        _copyinto(self.calls, analyzer.calls)
        _copyinto(self.warnings, analyzer.warnings)
        self.templates[key] = (body, end_ctx)
        return end_ctx, None

    def rewrite(self):
        """
        Pushes inferences about templates back into the original name to
        body map.
        """

        contextualized_names = {}
        def contextualize_name(tmpl_name, start_ctx):
            """
            Produces a distinct name for a template in a given context so
            that cloned bodies can be distinguished from the original and we
            can rewrite calls based on the context in which they appear.
            This allows templates to call helper templates in
            multiple contexts.
            """
            if start_ctx == self.start_state:
                return tmpl_name
            key = (tmpl_name, start_ctx)
            contextualized_name = contextualized_names.get(key)
            if contextualized_name is None:
                base_contextualized_name = '%s$%s' % (
                    tmpl_name,
                    debug.context_to_string(start_ctx).replace(' ', ','))
                contextualized_name = base_contextualized_name
                counter = 0
                # ensure uniqueness by looking into name_to_body
                while contextualized_name in self.name_to_body:
                    contextualized_name = '%s%d' % (
                        base_contextualized_name, counter)
                    counter += 1
                contextualized_names[key] = contextualized_name
            return contextualized_name

        def rewrite_node(node):
            """
            Rewrites pipelines and template calls in a template body by walking
            the node tree under the body.
            """
            if node in self.interps:
                pipeline, esc_modes = self.interps[node]
                required = [escaping.SANITIZER_FOR_ESC_MODE[esc_mode].__name__
                            for esc_mode in esc_modes]
                ensure_pipeline_contains(pipeline, required)
                node = node.with_pipeline(pipeline)
            if node in self.calls:
                call_ctx = self.calls[node]
                callee = node.to_callee()
                out_callee = contextualize_name(callee, call_ctx)
                if out_callee != callee:
                    node = node.with_callee(out_callee)
            changed = False
            children = []
            for child in node.children():
                out_child = rewrite_node(child)
                if out_child is not child:
                    changed = True
                children.append(out_child)
            if changed:
                node = node.with_children(children)
            return node

        for ((tmpl_name, start_ctx), (body, _)) in self.templates.iteritems():
            contextualized_name = contextualize_name(tmpl_name, start_ctx)
            self.name_to_body[contextualized_name] = rewrite_node(body)


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
    fn_name_a = _CANON_NAMES.get(fn_name_a, fn_name_a)
    fn_name_b = _CANON_NAMES.get(fn_name_b, fn_name_b)
    return fn_name_a == fn_name_b


def _copyinto(dest, src):
    """
    Copies all elements from a source set/dict/series into a
    destination set/dict/list.
    """
    if type(dest) is dict:
        if type(src) is dict:
            src = src.iteritems()
        for key, value in src:
            dest[key] = value
    elif type(dest) is set:
        for value in src:
            dest.add(value)
    else:
        dest.extend(list(src))


_CANON_NAMES = {
    'escape_html_attribute': 'escape_html',
    }
