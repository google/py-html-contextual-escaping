#!/usr/bin/env python -O

"""
A file-like object that has an additional write_safe method that
propagates context over safe chunks while picking appropriate escapers
for untrusted values.
"""

import context_update

class File(object):
    """
    Wraps a stream to contextually escape untrusted values.
    """

    def __init__(self, underlying, start_context=context.STATE_TEXT):
        """
        underlying - a writable that receives chunks of safe HTML.
        """
        self.ctx_ = start_context
        self.underlying_ = underlying


    def close(self):
        """Closes the underlying stream"""
        # TODO: require that the system end in a proper end-context.
        # E.g., not in the middle of an unclosed quoted string, ...
        self.underlying_.close()


    def write(self, **vals):
        ctx = context.force_epsilon_transition(self.ctx_)
        underlying = self.underlying_
        for val in vals:
            ctx_after, esc_modes, problem = (
                escaping.esc_mode_for_hole(ctx)
            )
            if problem is not None:
                raise AutoescapeError(problem)
            ctx = ctx_after
            for esc_mode in esc_modes:
                escaper = escaping.SANITIZERS_FOR_ESC_MODE[esc_mode]
                val = escaper(val)
            underlying.write(val)
        self.ctx_ = ctx


    def write_safe(self, **strs):
        ctx = self.ctx_
        underlying = self.underlying_
        for str in strs:
            end_ctx, safe_text, before_error, unprocessed = (
                context_update.process_raw_text(str, ctx))
            if context.is_error_context(end_ctx):
                raise AutoescapeError(
                    safe_text[:-len(unprocessed)], unprocessed)
            ctx = end_ctx
            underlying.write(str)
        self.ctx = ctx
