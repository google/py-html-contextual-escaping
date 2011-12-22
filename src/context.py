#!/usr/bin/python

"""
Defines a series of symbolic name groups which allow us to represent a context
in an HTML document as a number.
"""


def state_of(context):
    """
    The STATE_* portion of the given context.
    The state is a coarse-grained description of the parser state.
    """
    return context & STATE_ALL

def is_error_context(context):
    """True iff the state of the context is STATE_ERROR."""
    return state_of(context) == STATE_ERROR

# Outside an HTML tag, directive, or comment.  (Parsed character data).
STATE_TEXT = 0

# Inside an element whose content is RCDATA where text and entities
# can appear but where nested elements cannot.
# The content of "<title>" and "<textarea>" fall into
# this category since they cannot contain nested elements in HTML.
STATE_RCDATA = 1

# Just before a tag name.
STATE_HTML_BEFORE_TAG_NAME = 2

# Inside a tag name.
STATE_TAG_NAME = 3

# Before an HTML attribute or the end of a tag.
STATE_TAG = 4

# Inside an HTML attribute name.
STATE_ATTR_NAME = 5

STATE_AFTER_NAME = 6

# Following an equals sign ('=') after an attribute name in an HTML tag.
STATE_BEFORE_VALUE = 7

# Inside an HTML comment.
STATE_HTMLCMT = 8

# Inside a normal (non-CSS, JS, or URL) HTML attribute value.
STATE_ATTR = 9

# In CSS content outside a comment, string, or URL.
STATE_CSS = 10

# In CSS inside a // line comment.
STATE_CSSLINE_CMT = 11

# In CSS inside a /* block comment */.
STATE_CSSBLOCK_CMT = 12

# In CSS inside a "double quoted string".
STATE_CSSDQ_STR = 13

# In CSS inside a 'single quoted string'.
STATE_CSSSQ_STR = 14

# In CSS in a URL terminated by the first close parenthesis.
STATE_CSS_URL = 15

# In CSS in a URL terminated by the first double quote.
STATE_CSSDQ_URL = 16

# In CSS in a URL terminated by the first single quote.
STATE_CSSSQ_URL = 17

# In JavaScript, outside a comment, string, or Regexp literal.
STATE_JS = 18

# In JavaScript inside a // line comment.
STATE_JSLINE_CMT = 19

# In JavaScript inside a /* block comment */.
STATE_JSBLOCK_CMT = 20

# In JavaScript inside a "double quoted string".
STATE_JSDQ_STR = 21

# In JavaScript inside a 'single quoted string'.
STATE_JSSQ_STR = 22

# In JavaScript inside a /regular expression literal/.
STATE_JSREGEXP = 23

# In an HTML attribute whose content is a URL.
STATE_URL = 24

# Not inside any valid HTML/CSS/JS construct.
STATE_ERROR = 25

COUNT_OF_STATES = 26

# All of the state bits set.
STATE_ALL = 31


def element_type_of(context):
    """
    The ELEMENT_* portion of context.
    These values describe the type of HTML element in which context appears.
    """
    return context & ELEMENT_ALL

# No element or not a special element.
ELEMENT_NONE = 0

# A script element whose content is raw JavaScript.
ELEMENT_SCRIPT = 1 << 5

# A style element whose content is raw CSS.
ELEMENT_STYLE = 2 << 5

# A textarea element whose content is encoded HTML but which cannot contain
# elements.
ELEMENT_TEXTAREA = 3 << 5

# A title element whose content is encoded HTML but which cannot contain
# elements.
ELEMENT_TITLE = 4 << 5

# A listing element whose content is raw CDATA.
ELEMENT_LISTING = 5 << 5

# An XMP element whose content is raw CDATA.
ELEMENT_XMP = 6 << 5

# All of the element bits set.
ELEMENT_ALL = 7 << 5


def attr_type_of(context):
    """
    The ATTR_* portion of context.
    These values describe the content of the HTML attribute in which the
    context appears.
    """
    return context & ATTR_ALL

# No attribute or an attribute whose context is human readable or other
# non-structured plain text or keyword values.
ATTR_NONE = 0

# Mime-type text/javascript.
ATTR_SCRIPT = 1 << 8

# Mime-type text/css.
ATTR_STYLE = 2 << 8

# A URL or URL reference.
ATTR_URL = 3 << 8

# All of the attribute type bits set.
ATTR_ALL = 3 << 8


def delim_type_of(context):
    """
    The DELIM_* portion of context.

    These values describe the content that will end the HTML attribute in
    which context appears.
    """
    return context & DELIM_ALL

# Not in an attribute.
DELIM_NONE = 0

# "
DELIM_DOUBLE_QUOTE = 1 << 10

# '
DELIM_SINGLE_QUOTE = 2 << 10

# A space or '>' symbol.
DELIM_SPACE_OR_TAG_END = 3 << 10

# All of the delimiter type bits set.
DELIM_ALL = 3 << 10

# Maps DELIM_* to the text used to delimit attributes of that type.
DELIM_TEXT = {
    DELIM_DOUBLE_QUOTE: '"',
    DELIM_SINGLE_QUOTE: "'",
    DELIM_SPACE_OR_TAG_END: "",
    }


def js_ctx_of(context):
    """
    The JS_CTX_* portion of context.

    These values describes what a slash ('/') means when parsing JavaScript
    source code.  A slash that is not followed by another slash or an
    asterisk ('*') can either start a regular expression literal
    or start a division operator.

    This determination is made based on the full grammar, but Waldemar
    defined a very close to accurate grammar for a JavaScript 1.9 draft
    based purely on a regular lexical grammar which is what we use in
    the autoescaper.

    See also context_update.is_regex_preceder
    """
    return context & JS_CTX_ALL

# Not in JavaScript.
JS_CTX_NONE = 0

# A slash as the next token would start a regular expression literal.
JS_CTX_REGEX = 1 << 12

# A slash as the next token would start a division operator.
JS_CTX_DIV_OP = 2 << 12

# We do not know what a slash as the next token would start so it is
# an error for the next token to be a slash.
JS_CTX_UNKNOWN = 3 << 12

# All of the JS following slash bits set.
JS_CTX_ALL = 3 << 12


def url_part_of(context):
    """
    The URL_PART_* portion of context.

    These values describe the part of a URL reference in which context occurs.

    We need to distinguish these so that we can:
    1. normalize well-formed URIs that appear before the query,
    2. encode raw values interpolated as query parameters or keys,
    3. filter out values that specify a scheme like \"javascript:\".
    """
    return context & URL_PART_ALL

# Not in a URL or at the start, the ^ in "^http://auth/path?k=v#frag"..
URL_PART_NONE = 0

# In the scheme, authority, or path.
# Between ^s in "h^ttp://host/path^?k=v#frag".
URL_PART_PRE_QUERY = 1 << 14

# In the query portion.  Between ^s in "http://host/path?^k=v#frag^".
URL_PART_QUERY_OR_FRAG = 2 << 14

# In a URL, but not clear where.  Used to join different contexts.
URL_PART_UNKNOWN = 3 << 14

# All of the URL part bits set.
URL_PART_ALL = 3 << 14
