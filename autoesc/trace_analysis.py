#!/usr/bin/env python -O

"""
Support code for the trace_analysis algorithm below.

path_end_states = []
for each path through a node:
  path_state = state
  for each step in that path:
      path_state = analyzer.step(step, path_state)
      if path_state is None:
          break
  if path_state is not None:
      # None means that the path does not terminate normally.
      path_end_states.append(path_state)
if not path_end_states:
  return None  # No normal exit.
return analyzer.join(*path_end_states)

start_state - the initial state for the passes through this node.

A state should support == so that loops can test whether or not the state
reaches a steady state.

Returns the state after this node.
"""


class Analyzer(object):
    """
    An object that can propagate states and take side-effects based on
    the traces through a template.
    """

    def step(self, start_state, step_value, debug_hint=None):
        """
        step_value - an object that implements zero or more of
          1. to_pipeline() -> template.Pipeline
          2. to_raw_content() -> str|unicode
          3. to_callee() -> template name

        Values that return a non-None value from to_pipeline() must
        provide a with_pipeline(pipeline) methods that returns a clone
        but with any inserted pipeline elements.

        Values that return a non-None value from to_raw_content() must
        provide a with_raw_content(str) methods that returns a clone
        but with the given raw content instead.

        Values that return a non-None value from to_callee() must
        provide a with_callee(callee) that returns a clone but with the
        given callee.

        Returns the state after the step_value.
        """
        raise NotImplementedError('abstract')  # pragma: no cover

    def join(self, states, debug_hint=None):
        """
        Finds the bottom of the given states.
        """
        raise NotImplementedError('abstract')  # pragma: no cover

    def no_steady_state(self, states, debug_hint=None):
        """
        Indicates that a re-entrant construct is not analyzable because it
        does not reach a steady state -- there is no finite size graph
        (edges are state transitions) that describes the traces through it.

        Returns an error state or some other state that can be used to
        transmit this fact to the top caller.
        """
        raise NotImplementedError('abstract')  # pragma: no cover
