"""
Utility functions that aid in debugging context propagation problems.
"""

import context

def _context_enum_name_table(prefix):
    """
    Given 'FOO_' produces a table mapping
    the value of context.FOO_XYZ to 'FOO_XYZ'.
    """
    name_table = {}
    for key, value in context.__dict__.iteritems():
        if (key.startswith(prefix)
            and type(value) is int
            and value not in name_table):
            name_table[value] = key
    return name_table

_STATE_NAMES = _context_enum_name_table('STATE_')
_ELEMENT_NAMES = _context_enum_name_table('ELEMENT_')
_ATTR_NAMES = _context_enum_name_table('ATTR_')
_DELIM_NAMES = _context_enum_name_table('DELIM_')
_JS_CTX_NAMES = _context_enum_name_table('JS_CTX_')
_URL_PART_NAMES = _context_enum_name_table('URL_PART_')

def context_to_string(ctx):
    """
    Used in debug mode to convert a context represented as an integer to a
    diagnostic string.
    """
    state = context.state_of(ctx)
    element = context.element_type_of(ctx)
    attr = context.attr_type_of(ctx)
    delim = context.delim_type_of(ctx)
    js_ctx = context.js_ctx_of(ctx)
    url_part = context.url_part_of(ctx)

    parts = [_STATE_NAMES[state],
             element and _ELEMENT_NAMES[element],
             attr and _ATTR_NAMES[attr],
             delim and _DELIM_NAMES[delim],
             js_ctx and _JS_CTX_NAMES[js_ctx],
             url_part and _URL_PART_NAMES[url_part],
             ]
    return "[Context %s]" % " ".join(
        [part or 'UNKNOWN' for part in parts if part])
