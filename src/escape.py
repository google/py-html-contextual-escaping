#!/usr/bin/env python -O

"""
Implements the HTML contextual escaping algorithm as defined at
http://js-quasis-libraries-and-repl.googlecode.com/svn/trunk/safetemplate.html
"""

import context
import context_update
import debug
import escaping
import functools
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
            analyzer.error(
                None,
                'template %s does not start and end in the same context: %s'
                % (name, debug.context_to_string(end_state)))
            has_errors = True

    if has_errors:
        raise EscapeError('\n'.join(analyzer.errors))

    analyzer.rewrite()


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
        # Maps interpolation nodes to pipelines and escaping modes
        self.interps = {}
        # Maps text nodes to replacement text.
        self.text_values = {}
        # Maps external calls (step_values) to the contexts
        # in which they occur.
        # This assumes that cloned() step_values are distinct
        # from the original.
        self.calls = {}
        # Messages that explain failure to escape.
        self.errors = []

    def error(self, debug_hint, msg):
        """Queues a message explaining a problem noticed during escaping."""
        if debug_hint:
            msg = '%s: %s' % (debug_hint, msg)
        self.errors.append(msg)

    def step(self, start_state, step_value, debug_hint=None):
        if context.is_error_context(start_state):
            # Simplifies error checking below.
            return start_state
        if hasattr(step_value, 'to_raw_content'):
            # Handle text nodes specified by the template author.
            raw_content = step_value.to_raw_content()
            if raw_content is not None:
                try:
                    end_state, new_content, error_ctx, error_text = (
                        context_update.process_raw_text(
                            raw_content, start_state))
                    if context.is_error_context(end_state):
                        self.error(debug_hint, 'bad content in %s: `%s`' % (
                            debug.context_to_string(error_ctx), error_text))
                    elif new_content != raw_content:
                        self.text_values[step_value] = new_content
                except context_update.ContextUpdateFailure, err:
                    self.error(debug_hint, str(err))
                    end_state = context.STATE_ERROR
                return end_state
        if hasattr(step_value, 'to_pipeline'):
            # Handle interpolation of untrusted values.
            pipeline = step_value.to_pipeline()
            if pipeline is not None:
                end_state, esc_modes, problem = (
                    escaping.esc_mode_for_hole(start_state))
                self.interps[step_value] = pipeline, esc_modes
                if context.is_error_context(end_state):
                    if problem is None:
                        self.error(debug_hint, 'hole cannot appear in %s' % (
                            debug.context_to_string(start_state)))
                    else:
                        self.error(debug_hint, problem)
                return end_state
        if hasattr(step_value, 'to_callee'):
            # Handle calls to other templates by recursively typing the end
            # context of that template.
            callee = step_value.to_callee()
            if callee is not None:
                end_ctx = self.external_call(callee, start_state, debug_hint)
                self.calls[step_value] = start_state
                # rely on external_call to explain failure.
                return end_ctx
        return start_state

    def join(self, states, debug_hint=None):
        out_state = functools.reduce(context_update.context_union, states)
        if context.is_error_context(out_state):
            # Report an error only if none was reported when the states were
            # produced.
            for state in states:
                if context.is_error_context(state):
                    return out_state
            self.error(debug_hint, 'branches end in incompatible contexts: %s'
                       % ', '.join([debug.context_to_string(state)
                                    for state in states]))
        return out_state

    def external_call(self, tmpl_name, start_ctx, debug_hint=None):
        """
        Makes sure that the named template can be called in the given context
        and returns the context after a successful call to the template in the
        start context.
        """
        name_and_ctx = (tmpl_name, start_ctx)
        self.called.add(name_and_ctx)
        if name_and_ctx in self.templates:
            _, end_context = self.templates[name_and_ctx]
            return end_context
        body = self.name_to_body.get(tmpl_name)
        if body is None:
            self.error(debug_hint, 'no such template %s' % tmpl_name)
            return context.STATE_ERROR
        if start_ctx != self.start_state:
            # Derive a copy so that calls and pipelines can be written
            # independently of the original.
            body = body.clone()
        return self._compute_end_context(name_and_ctx, body, debug_hint)

    def no_steady_state(self, states, debug_hint=None):
        for state in states:
            if context.is_error_context(state):
                return state
        self.error(debug_hint, 'loop switches between states (%s)' % (
            ', '.join([debug.context_to_string(state) for state in states])))
        return context.STATE_ERROR

    def _compute_end_context(self, name_and_ctx, body, debug_hint):
        """Propagate context over the body."""
        tmpl_name, start_ctx = name_and_ctx
        ctx, problems = self._escape_template_body(
            name_and_ctx, start_ctx, body)
        if problems is not None:
            # Look for a fixed point by assuming c1 as the output context.
            ctx2, problems2 = self._escape_template_body(
                name_and_ctx, ctx, body)
            if problems2 is None:
                ctx, problems = ctx2, None
        if problems is not None:
            if not context.is_error_context(ctx):
                # We have not explained the problem yet.
                self.error(debug_hint,
                    "cannot compute output context for template %s in %s" % (
                        tmpl_name, debug.context_to_string(start_ctx)))
            self.errors.extend(problems)
            return context.STATE_ERROR
        return ctx

    def _escape_template_body(self, name_and_ctx, assumed_end_ctx, body):
        """
        escapes the given template assuming the given output context.

        It returns the best guess at an output context, and any problems
        encountered along the way or None on success.

        name_and_ctx - the name and start context suitable as a key into
            self.templates.
        assumed_end_ctx - a possible end context.

        Returns the best guess at the end context and a list of problems with
        that end context.  If the list of problems is None, then the end
        context is ok to use.
        """
        # We need to assume an output context so that recursive template calls
        # take the fast path out of escapeTree instead of infinitely recursing.
        # Naively assuming that the input context is the same as the output
        # works >90% of the time.
        self.templates[name_and_ctx] = (body, assumed_end_ctx)

        def ctx_filter(end_ctx, analyzer):
            """
            Checks the end context so we do not update self unless we can
            confidently compute an end context.

            end_ctx - the computed context after the call completes.
            analyzer - the analyzer used to type the body.
            """
            return not (
                context.is_error_context(end_ctx)
                # If the template is recursively called, end_ctx must be
                # consistent with our assumption.  Otherwise our assumption
                # didn't factor into the computation of end_ctx, so we can
                # just use end_ctx.
                or (name_and_ctx in analyzer.called
                    and assumed_end_ctx != end_ctx))

        _, start_ctx = name_and_ctx

        end_ctx, problems = self._escape_body_conditionally(
            start_ctx, body, ctx_filter)
        if problems is None:
            self.templates[name_and_ctx] = (body, end_ctx)
        else:
            self.templates[name_and_ctx] = (body, context.STATE_ERROR)
        return end_ctx, problems

    def _escape_body_conditionally(
        self, start_ctx, body, ctx_filter=lambda ctx, analyzer: True):
        """
        Speculatively compute the end context of body starting in the given
        start context, and if the end context passes filter, fold any typing
        conclusions into self.
        """

        # Derive an analyzer so we can see if our assumptions hold before
        # committing to them.
        analyzer = _Analyzer(self.name_to_body, self.start_state,
                             templates=self.templates)
        end_ctx = body.reduce_traces(start_ctx, analyzer)

        if not ctx_filter(end_ctx, analyzer):
            return end_ctx, analyzer.errors            

        # Copy inferences and pending changes from analyzer back into self.
        _copyinto(self.templates, analyzer.templates)
        _copyinto(self.called, analyzer.called)
        _copyinto(self.text_values, analyzer.text_values)
        _copyinto(self.interps, analyzer.interps)
        _copyinto(self.calls, analyzer.calls)
        _copyinto(self.errors, analyzer.errors)
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
            if node in self.text_values:
                new_content = self.text_values[node]
                node = node.with_raw_content(new_content)
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
            children = tuple(node.children())
            rewritten_children = tuple(
                [rewrite_node(child) for child in children])
            if children != rewritten_children:
                node = node.with_children(rewritten_children)
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

    el_pos = 0
    while True:
        element = pipeline.element_at(el_pos)
        if element is None:
            break
        if element == 'noescape':
            # Don't interfere if there is a pipeline element noescape.
            # TODO: Maybe move this convention into the templating language.
            # The templating language just ignores pipeline changes if there is
            # an element named 'noescape' or whatever flavor it chooses.
            return
        el_pos += 1

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


class EscapeError(BaseException):
    """
    A failure to escape a template or templates.
    """

    def __init__(self, msg):
        BaseException.__init__(self, msg)
