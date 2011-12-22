#!/usr/bin/python

"""
Definitions of sanitization functions and sanitized content wrappers.
See http://js-quasis-libraries-and-repl.googlecode.com/svn/trunk
    /safetemplate.html#sanitization_functions
for definitions of sanitization functions and sanitized content wrappers.

These sanitization functions correspond to values of the ESC_MODE_* enum
defined in the context module.
"""

import content
import context
import json
import re


# Encodes HTML special characters.
ESC_MODE_ESCAPE_HTML = 0

# Like ESC_MODE_ESCAPE_HTML but normalizes known safe HTML since RCDATA can't
# contain tags.
ESC_MODE_ESCAPE_HTML_RCDATA = 1

# Encodes HTML special characters, including quotes, so that the
# value can appear as part of a quoted attribute value.  This differs
# from ESCAPE_MODE_ESCAPE_HTML in that it strips tags from known safe
# HTML.
ESC_MODE_ESCAPE_HTML_ATTRIBUTE = 2

# Only allow a valid identifier - letters, numbers, dashes, and underscores.
# Throws an exception otherwise.
ESC_MODE_FILTER_HTML_ELEMENT_NAME = 3

# Only allow a valid identifier - letters, numbers, dashes, and underscores.
# Throws an exception otherwise.
ESC_MODE_FILTER_HTML_ATTRIBUTE = 4

# Encode all HTML special characters and quotes, and JS newlines as
# if to allow them to appear literally in a JS string.
ESC_MODE_ESCAPE_JS_STRING = 5

# If a number or boolean, output as a JS literal.  Otherwise surround
# in quotes and escape.  Make sure all HTML and space characters are
# quoted.
ESC_MODE_ESCAPE_JS_VALUE = 6

# Like ESC_MODE_ESCAPE_JS_STRING but additionally escapes RegExp specials like
# ".+*?$^[](){}".
ESC_MODE_ESCAPE_JS_REGEX = 7

# Must escape all quotes, newlines, and the close parenthesis using
# '\\' followed by hex followed by a space.
ESC_MODE_ESCAPE_CSS_STRING = 8

# If the value is numeric, renders it as a numeric value so that
# "{$n}px" works as expected, otherwise if it is a valid
# CSS identifier, outputs it without escaping, otherwise surrounds in
# quotes and escapes like ESC_MODE_ESCAPE_CSS_STRING.
ESC_MODE_FILTER_CSS_VALUE = 9

# Percent encode all URL special characters and characters that
# cannot appear unescaped in a URL such as spaces.  Make sure to
# encode pluses and parentheses.
# This corresponds to the JavaScript function encodeURIComponent.
ESC_MODE_ESCAPE_URL = 10

# Percent encode non-URL characters that cannot appear unescaped in a
# URL such as spaces, and encode characters that are not special in
# URIs that are special in languages that URIs are embedded in such
# as parentheses and quotes.  This corresponds to the JavaScript
# function encodeURI but additionally encodes quotes
# parentheses, and percent signs that are not followed by two hex
# digits.
ESC_MODE_NORMALIZE_URL = 11

# Filters out URL schemes like "javascript:" that load code.
ESC_MODE_FILTER_URL = 12

# The explicit rejection of escaping.
ESC_MODE_NO_AUTOESCAPE = 13

# A mapping from all inputs to a single space.
ESC_MODE_ELIDE = 14

# Introduces a double quote at the beginning for interpolation values
# that start an open quoted HTML_ATTRIBUTE
ESC_MODE_OPEN_QUOTE = 15

# One greater than the max of ESC_MODE_*.
_COUNT_OF_ESC_MODES = 16

# Contains pairs such that (f, g) is in this set only (but not necessarily)
# if g(f(x)) == f(x) for all x.
REDUNDANT_ESC_MODES = set([
    (ESC_MODE_ELIDE, ESC_MODE_ESCAPE_HTML_ATTRIBUTE),
    (ESC_MODE_ELIDE, ESC_MODE_ESCAPE_HTML),
    (ESC_MODE_ESCAPE_CSS_STRING, ESC_MODE_ESCAPE_HTML_ATTRIBUTE),
    (ESC_MODE_ESCAPE_JS_REGEX, ESC_MODE_ESCAPE_HTML_ATTRIBUTE),
    (ESC_MODE_ESCAPE_JS_STRING, ESC_MODE_ESCAPE_HTML_ATTRIBUTE),
    (ESC_MODE_ESCAPE_URL, ESC_MODE_NORMALIZE_URL),
    ])


ESC_MODE_FOR_STATE = [None for _ in xrange(0, context.COUNT_OF_STATES)]
ESC_MODE_FOR_STATE[context.STATE_TEXT] = ESC_MODE_ESCAPE_HTML
ESC_MODE_FOR_STATE[context.STATE_RCDATA] = ESC_MODE_ESCAPE_HTML_RCDATA
ESC_MODE_FOR_STATE[context.STATE_HTML_BEFORE_TAG_NAME] = (
    ESC_MODE_FILTER_HTML_ELEMENT_NAME)
ESC_MODE_FOR_STATE[context.STATE_TAG_NAME] = ESC_MODE_FILTER_HTML_ELEMENT_NAME
ESC_MODE_FOR_STATE[context.STATE_TAG] = ESC_MODE_FILTER_HTML_ATTRIBUTE
ESC_MODE_FOR_STATE[context.STATE_ATTR_NAME] = ESC_MODE_FILTER_HTML_ATTRIBUTE
ESC_MODE_FOR_STATE[context.STATE_HTMLCMT] = ESC_MODE_ELIDE
ESC_MODE_FOR_STATE[context.STATE_ATTR] = ESC_MODE_ESCAPE_HTML_ATTRIBUTE
ESC_MODE_FOR_STATE[context.STATE_CSS] = ESC_MODE_FILTER_CSS_VALUE
ESC_MODE_FOR_STATE[context.STATE_CSSLINE_CMT] = ESC_MODE_ELIDE
ESC_MODE_FOR_STATE[context.STATE_CSSBLOCK_CMT] = ESC_MODE_ELIDE
ESC_MODE_FOR_STATE[context.STATE_CSSDQ_STR] = ESC_MODE_ESCAPE_CSS_STRING
ESC_MODE_FOR_STATE[context.STATE_CSSSQ_STR] = ESC_MODE_ESCAPE_CSS_STRING
ESC_MODE_FOR_STATE[context.STATE_CSS_URL] = ESC_MODE_NORMALIZE_URL
ESC_MODE_FOR_STATE[context.STATE_CSSDQ_URL] = ESC_MODE_NORMALIZE_URL
ESC_MODE_FOR_STATE[context.STATE_CSSSQ_URL] = ESC_MODE_NORMALIZE_URL
ESC_MODE_FOR_STATE[context.STATE_JS] = ESC_MODE_ESCAPE_JS_VALUE
ESC_MODE_FOR_STATE[context.STATE_JSLINE_CMT] = ESC_MODE_ELIDE
ESC_MODE_FOR_STATE[context.STATE_JSBLOCK_CMT] = ESC_MODE_ELIDE
ESC_MODE_FOR_STATE[context.STATE_JSDQ_STR] = ESC_MODE_ESCAPE_JS_STRING
ESC_MODE_FOR_STATE[context.STATE_JSSQ_STR] = ESC_MODE_ESCAPE_JS_STRING
ESC_MODE_FOR_STATE[context.STATE_JSREGEXP] = ESC_MODE_ESCAPE_JS_REGEX
ESC_MODE_FOR_STATE[context.STATE_URL] = ESC_MODE_ESCAPE_HTML_ATTRIBUTE


def esc_mode_for_hole(context_before):
    """
    Given a context in which an untrusted value hole appears, computes the
    escaping modes needed to render that untrusted value safe for interpolation
    and the context after the hole.
    
    context_before - The input context before the substitution.

    Returns (context after, (escaping_modes...,))
    """
    ctx = context.force_epsilon_transition(context_before)
    state, url_part = context.state_of(ctx), context.url_part_of(ctx)
    esc_modes = [ESC_MODE_FOR_STATE[state]]
    problem = None

    if url_part == context.URL_PART_NONE:
        # Make sure that at the start of a URL, we filter out dangerous
        # protocols.
        if state in (
            context.STATE_URL, context.STATE_CSS_URL, context.STATE_CSSDQ_URL,
            context.STATE_CSSSQ_URL):
            esc_modes = [ESC_MODE_FILTER_URL, ESC_MODE_NORMALIZE_URL]
            ctx = (ctx & ~context.URL_PART_ALL) | context.URL_PART_PRE_QUERY
        elif state in (context.STATE_CSSDQ_STR, context.STATE_CSSSQ_STR):
            esc_modes[:0] = [ESC_MODE_FILTER_URL]
            ctx = (ctx & ~context.URL_PART_ALL) | context.URL_PART_PRE_QUERY
    elif url_part == context.URL_PART_PRE_QUERY:
        if state not in (context.STATE_CSSDQ_STR, context.STATE_CSSSQ_STR):
            esc_modes[0] = ESC_MODE_NORMALIZE_URL
    elif url_part == context.URL_PART_QUERY_OR_FRAG:
        esc_modes[0] = ESC_MODE_ESCAPE_URL
    elif url_part == context.URL_PART_UNKNOWN:
        ctx = context.STATE_ERROR
        problem = 'hole appears in an ambiguous URL context'

    if state == context.STATE_JS:
        ctx = (ctx & ~context.JS_CTX_ALL) | context.JS_CTX_DIV_OP

    esc_mode = esc_modes[-1]
    delim_type = context.delim_type_of(ctx)
    if delim_type != context.DELIM_NONE:
        # Figure out how to escape the attribute value.
        if esc_mode != ESC_MODE_ESCAPE_HTML_ATTRIBUTE:
            esc_modes.append(ESC_MODE_ESCAPE_HTML_ATTRIBUTE)
        if (context.delim_type_of(context_before) == context.DELIM_NONE
            and delim_type == context.DELIM_SPACE_OR_TAG_END):
            esc_modes.append(ESC_MODE_OPEN_QUOTE)

    last, i = esc_modes[0], 1
    while i < len(esc_modes):
        curr = esc_modes[i]
        # If, for all x, f(g(x)) == g(x), we can skip f.
        if (last, curr) in REDUNDANT_ESC_MODES:
            esc_modes[i:i+1] = []
        else:
            last = curr
            i += 1
    return ctx, tuple(esc_modes), problem


def escape_html(value):
    """
    Escapes HTML special characters in a string.  Escapes double quote '\"' in
    addition to '&', '<', and '>' so that a string can be included in an HTML
    tag attribute value within double quotes.
    Will emit known safe HTML as-is.

    value - The string-like value to be escaped.  May not be a string,
            but the value will be coerced to a string.

    Returns an escaped version of value.
    """

    if value is None:
        return ""
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_HTML):
        return value.content
    if type(value) not in (str, unicode):
        value = str(value)
    return _escape_html_helper(value)


def escape_html_rcdata(value):
    """
    Escapes HTML special characters in a string so that it can be embedded in
    RCDATA.

    Escapes HTML special characters so that the value will not prematurely end
    the body of a tag like <textarea> or <title>.
    RCDATA tags cannot contain other HTML elements, so it is not strictly
    necessary to escape HTML special characters except when part of that text
    looks like an HTML entity or like a close tag : "</textarea>".

    Will normalize known safe HTML to make sure that sanitized HTML (which could
    contain an innocuous "</textarea>" don't prematurely end an RCDATA
    element.

    value - The string-like value to be escaped.  May not be a string,
            but the value will be coerced to a string.

    Returns An escaped version of value.
    """

    if value is None:
        return ""
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_HTML):
        return _normalize_html_helper(value.content)
    if type(value) not in (str, unicode):
        value = str(value)
    return _escape_html_helper(value)


def _strip_html_tags(value):
    """
    Removes HTML tags from a string of known safe HTML so it can be used as an
    attribute value.

    value - The HTML to be escaped.

    Returns a representation of value without tags, HTML comments, or
    other content.
    """
    return _HTML_TAG_REGEX.sub("", value)


def escape_html_attribute(value):
    """
    Escapes HTML special characters in an HTML attribute value.

    value - The HTML to be escaped.  May not be a string, but the
        value will be coerced to a string.

    Returns An escaped version of value.
    """
    if value is None:
        return ""
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_HTML):
        return _normalize_html_helper(_strip_html_tags(value.content))
    if type(value) not in (str, unicode):
        value = str(value)
    return _escape_html_helper(value)


def filter_html_attribute(value):
    """
    Filters out strings that cannot be a substring of a valid HTML attribute.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a valid HTML attribute name part or name/value pair.
    \"zSafehtmlz\" if the input is invalid.
    """

    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_HTML_ATTR):
        # TODO: Normalize quotes and surrounding space.
        return value.content
    if type(value) not in (str, unicode):
        value = str(value)
    value = _filter_html_attribute_helper(value)
    equals_index = value.find('=')
    if equals_index >= 0 and value[-1] not in ('"', "'"):
        # Quote any attribute values so that a contextually autoescaped
        # whole attribute does not end up having a following value
        # associated with it.
        # The contextual autoescaper, since it propagates context left to
        # right, is unable to distinguish
        #     <div {$x}>
        # from
        #     <div {$x}={$y}>.
        # If {$x} is "dir=ltr", and y is "foo" make sure the parser does not
        # see the attribute "dir=ltr=foo".
        return '%s"%s"' % (value[:equals_index+1], value[equals_index+1:])
    return value


def filter_html_element_name(value):
    """
    Filters out strings that cannot be a substring of a valid HTML element name.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a valid HTML element name part.
    \"zSafehtmlz\" if the input is invalid.
    """
    if type(value) not in (str, unicode):
        value = str(value)
    return _filter_element_name_helper(value)


def escape_js_string(value):
    """
    Escapes characters in the value to make it valid content for a JS string
    literal.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """

    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_JS_STR_CHARS):
        return _normalize_js_string_helper(value.content)
    if type(value) not in (str, unicode):
        value = str(value)
    return _escape_js_string_helper(value)


def _marshal_json_obj(obj):
    """
    Marshals a JSON object by looking for a to_json method.
    """
    if hasattr(obj, 'to_json'):
        try:
            return obj.to_json()
        except (StandardError, Warning):
            pass
    elif hasattr(obj, '__unicode__'):
        return unicode(obj)
    elif hasattr(obj, '__str__'):
        return str(obj)
    return None


def escape_js_value(value):
    """
    Encodes a value as a JavaScript literal.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a JavaScript code representation of the input.
    """

    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_JS):
        value = value.content
        # We can't allow a value that contains the substring '</script'.
        # We could try to fixup, but that is problematic.
        if re.search(r'(?i)</script', value):
            value = None
        return value

    escaped = json.dumps(
        value,
        ensure_ascii=True,  # Encodes JS newlines U+2028 and U+2029
        check_circular=True,  # Don't allow denial of service via cyclic vals.
        allow_nan=True,  # NaN is ok in JS.
        indent=None,
        default=_marshal_json_obj,
        separators=(',', ':'))
    # Could provide default(obj) to convert user-defined classes to dicts.

    if not len(escaped):  # Paranoia.
        return " null "
    char0 = escaped[0]
    if char0 == '{':
        # There is a higher risk that {...} will be interpreted as a block than
        # that the parentheses will introduce a function call.
        escaped = '(%s)' % escaped
    elif char0 not in '["':
        # "true" -> " true "
        # We surround values with spaces so that they can't be interpolated into
        # identifiers by accident.
        # We could use parentheses but those might be interpreted as a function
        # call.
        escaped = ' %s ' % escaped
    # Prevent string content from being interpreted as containing HTML token
    # boundaries.
    return escaped.replace('<', r'\x3c').replace('>', r'\x3e')


def escape_js_regex(value):
    """
    Escapes characters in the string to make it valid content for a JS regular
    expression literal.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_JS_STR_CHARS):
        return _normalize_js_regex_helper(value.content)

    if value is None:
        escaped = ""
    else:
        if type(value) not in (str, unicode):
            value = str(value)
        escaped = _escape_js_regex_helper(value)

    if not escaped:
        # Matches nothing but does not cause /{$foo}/ to become a line-comment
        # when $foo is the empty string.
        escaped = "(?:)"
    return escaped


# unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"
_NOT_URL_UNRESERVED = re.compile(r"[^0-9A-Za-z\._~\-]+")

def _pct_encode(match):
    """URL encodes octets in value"""
    value = match.group(0)
    if type(value) is unicode:
        value = value.encode('UTF-8')
    if len(value) == 1:
        return '%%%02x' % ord(value)
    return "".join(["%%%02x" % ord(char) for char in value])

def escape_url(value):
    """
    Escapes a string so that it can be safely included in a URL.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """

    if value is None:
        return ""
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_URL):
        return normalize_url(value.content)
    if type(value) not in (str, unicode):
        value = str(value)

    return _NOT_URL_UNRESERVED.sub(_pct_encode, value)



# Matches all characters that are neither reserved nor unreserved
#    unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
#    reserved      = gen-delims / sub-delims
#    gen-delims    = ":" / "/" / "?" / "#" / "[" / "]" / "@"
#    sub-delims    = "!" / "$" / "&" / "'" / "(" / ")"
#                  / "*" / "+" / "," / ";" / "="
# and those that are HTML attribute delimiters or that cannot appear in a CSS
# url.
# From http://www.w3.org/TR/CSS2/grammar.html : G.2: CSS grammar:
#
#         url        ([!#$%&*-~]|{nonascii}|{escape})*
# This does match '(', ')', and '\'' because those characters are special in
# HTML &| CSS.
# Apostophes and parentheses are not matched by encodeURIComponent.
# They are technically special in URIs, but only appear in the obsolete mark
# production in Appendix D.2 of RFC 3986, so can be encoded without changing
# semantics.
_NOT_URL_UNRESERVED_AND_SPECIAL = re.compile(
    r"(?:[^0-9A-Za-z\._~:/?#\[\]@!$&*+,;=%\-]|%(?![0-9A-Fa-f]{2}))+")

def normalize_url(value):
    """
    Removes rough edges from a URL by escaping any raw
    HTML/JS string delimiters.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """

    if value is None:
        return ""
    if type(value) not in (str, unicode):
        value = str(value)

    return _NOT_URL_UNRESERVED_AND_SPECIAL.sub(_pct_encode, value)


def filter_url(value):
    """
    Vets a URL's protocol and removes rough edges from a URL by escaping
    any raw HTML/JS string delimiters.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_URL):
        # Pass through to escape_url or normalize_url with content kind intact.
        return value
    if value is None:
        value = ""
    elif type(value) not in (str, unicode):
        value = str(value)
    if not _FILTER_FOR_FILTER_URL.match(value):
        return "#zSafehtmlz"
    return value


def elide(_):
    """
    Since comments are elided from the static template text, we also elide
    the values interpolated into them.

    Always returns the empty string.
    """
    return ''


def open_quote(value):
    """
    When we encounter an interpolation hole like '<img src={{.}}>', we do an
    epsilon transition into an unquoted value state.

    This means that there is no readily available text node to which we can
    append a double quote character to normalize attribute quotes.

    So we add an escaper to the interpolation that prefixes the value with
    a quote.
    """
    return '"%s' % value


def escape_css_string(value):
    """
    Escapes a string so it can safely be included inside a quoted CSS string.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """
    if value is None:
        value = ""
    elif type(value) not in (str, unicode):
        value = str(value)
    return _escape_css_string_helper(value)


def filter_css_value(value):
    """
    Encodes a value as a CSS identifier part, keyword, or quantity.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a safe CSS identifier part, keyword, or quanitity.
    """

    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_CSS):
        return value

    if value is None:
        value = ""
    elif type(value) not in (str, unicode):
        value = str(value)

    decoded = _CSS_ESC.sub(_css_decode_one, value)

    # CSS3 error handling is specified as honoring string boundaries per
    # http://www.w3.org/TR/css3-syntax/#error-handling :
    #     Malformed declarations. User agents must handle unexpected
    #     tokens encountered while parsing a declaration by reading until
    #     the end of the declaration, while observing the rules for
    #     matching pairs of (), [], {}, "", and '', and correctly handling
    #     escapes. For example, a malformed declaration may be missing a
    #     property, colon (:) or value.
    # So we need to make sure that values do not have mismatched bracket
    # or quote characters to prevent the browser from restarting parsing
    # inside a string that might embed JavaScript source.
    if not _CSS_VALUE_DISALLOWED.search(decoded):
        id_chars = _NOT_ALPHANUMERIC.sub('', decoded).lower()
        if not _CSS_IDENT_DISALLOWED.search(id_chars):
            return decoded
    return 'zSafehtmlz'

_CSS_VALUE_DISALLOWED = re.compile(r'[\0"\'()/;@\[\\\]`{}<]|--')

_CSS_IDENT_DISALLOWED = re.compile(r'(?i)\A(?:expression|(moz)?binding)')

_NOT_ALPHANUMERIC = re.compile(r'[^A-Za-z0-9]+')

_CSS_ESC = re.compile(r'\\([0-9A-Fa-f]+)[\t\n\f\r ]?')


def _css_decode_one(match):
    """
    r'\a' -> '\n'.
    Expects hex digits in group 1 as per _CSS_ESC.
    """
    return unichr(int(match.group(1), 16))


_ESCAPE_MAP_FOR_HTML = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    }

def _replacer_for_html(match):
    """A regex replacer"""
    group = match.group(0)
    encoded = _ESCAPE_MAP_FOR_HTML.get(group)
    if encoded is None:
        encoded = "&#%d;" % ord(group)
        _ESCAPE_MAP_FOR_HTML[group] = encoded
    return encoded


_ESCAPE_MAP_FOR_ESCAPE_JS_STRING__AND__ESCAPE_JS_REGEX = {
    # We do not escape "\x08" to "\\b" since that means word-break in RegExps.
    "\x09": "\\t",
    "\x0a": "\\n",
    "\x0c": "\\f",
    "\x0d": "\\r",
    "/": "\\/",
    "\\": "\\\\",
    }

def _replacer_for_js(match):
    """A regex replacer."""
    group = match.group(0)
    encoded = _ESCAPE_MAP_FOR_ESCAPE_JS_STRING__AND__ESCAPE_JS_REGEX.get(group)
    if encoded is None:
        # "\u2028" -> "\\u2028"
        char_code = ord(group)
        if char_code < 0x100:
            encoded = r'\x%02x' % char_code
        else:
            encoded = r'\u%04x' % char_code
        _ESCAPE_MAP_FOR_ESCAPE_JS_STRING__AND__ESCAPE_JS_REGEX[group] = encoded
    return encoded

_ESCAPE_MAP_FOR_ESCAPE_CSS_STRING = {
    '\\': r'\\',
    }

def _replacer_for_css(match):
    """A regexp replacer."""
    group = match.group(0)
    encoded = _ESCAPE_MAP_FOR_ESCAPE_CSS_STRING.get(group)
    if encoded is None:
        encoded = r'\%x ' % ord(group)
        _ESCAPE_MAP_FOR_ESCAPE_CSS_STRING[group] = encoded
    return encoded


_MATCHER_FOR_ESCAPE_HTML = re.compile(r'[\x00"&\x27<>]')

_MATCHER_FOR_ESCAPE_HTML_SQ_ONLY = re.compile(r'[\x00&\x27<>]')

_MATCHER_FOR_ESCAPE_HTML_DQ_ONLY = re.compile(r'[\x00&"<>]')

_MATCHER_FOR_NORMALIZE_HTML = re.compile(r'[\x00"\x27<>]')

_MATCHER_FOR_ESCAPE_JS_STRING = re.compile(
    ur'[\x00\x08-\x0d"&\x27+/<=>\\\x7f\x85\u2028\u2029]')

_MATCHER_FOR_NORMALIZE_JS_STRING = re.compile(
    ur'[\x00\x08-\x0d"&\x27+/<=>\x7f\x85\u2028\u2029]|\\(?![^\n\r\u2028\u2029])')

_MATCHER_FOR_ESCAPE_JS_REGEX = re.compile(
    ur'[\x00\x08-\x0d"$&-+\--/:<-?\[-^\x7b-\x7d\x7f\x85\u2028\u2029]')

_MATCHER_FOR_NORMALIZE_JS_REGEX = re.compile(
    ur'[\x00\x08-\x0d"$&-+\--/:<-?\[\]-^\x7b-\x7d\x7f\x85\u2028\u2029]'
    ur'|\\(?![^\n\r\u2028\u2029])')

_MATCHER_FOR_ESCAPE_CSS_STRING = re.compile(
    ur'[\x00\x08-\x0d"&-*/:->@\\\x7b\x7d\x85\xa0\u2028\u2029]')

_FILTER_FOR_FILTER_URL = re.compile(
    r'(?i)^(?:(?:https?|mailto):|[^&:/?#]*(?:[/?#]|$))')

_FILTER_FOR_FILTER_HTML_ATTRIBUTE = re.compile(
    r'(?i)^(?!style|on|action|archive|background|cite|classid|codebase|data'
    r'|dsync|href|longdesc|src|usemap)(?:[a-z0-9_$:-]+|dir=(?:ltr|rtl))$')

_FILTER_FOR_FILTER_HTML_ELEMENT_NAME = re.compile(
    r'(?i)^(?!script|style|title|textarea|xmp|no)[a-z0-9_$:-]*$')

def _escape_html_helper(value):
    """ '<a&gt;' -> '&lt;a&amp;gt;' """
    return _MATCHER_FOR_ESCAPE_HTML.sub(_replacer_for_html, value)

def escape_html_sq_only(value):
    """ Escapes an HTML attribute value for embedding between single quotes."""
    return _MATCHER_FOR_ESCAPE_HTML_SQ_ONLY.sub(_replacer_for_html, value)

def escape_html_dq_only(value):
    """ Escapes an HTML attribute value for embedding between double quotes."""
    return _MATCHER_FOR_ESCAPE_HTML_DQ_ONLY.sub(_replacer_for_html, value)


def _normalize_html_helper(value):
    """ '<a&gt;' -> '&lt;a&gt;' """
    return _MATCHER_FOR_NORMALIZE_HTML.sub(_replacer_for_html, value)

def _escape_js_string_helper(value):
    """ '</script>' -> '\x3c/script\x3e' """
    return _MATCHER_FOR_ESCAPE_JS_STRING.sub(_replacer_for_js, value)

def _normalize_js_string_helper(value):
    """ '</script>' -> '\x3c/script\x3e' """
    return _MATCHER_FOR_NORMALIZE_JS_STRING.sub(_replacer_for_js, value)

def _escape_js_regex_helper(value):
    """ '</script>' -> '\x3c\x2fscript\x3e' """
    return _MATCHER_FOR_ESCAPE_JS_REGEX.sub(_replacer_for_js, value)

def _normalize_js_regex_helper(value):
    """ '</script>' -> '\x3c/script\x3e' """
    return _MATCHER_FOR_NORMALIZE_JS_REGEX.sub(_replacer_for_js, value)

def _escape_css_string_helper(value):
    """ '</style>' -> '\3c \2f style\3e ' """
    return _MATCHER_FOR_ESCAPE_CSS_STRING.sub(_replacer_for_css, value)

def _filter_html_attribute_helper(value):
    """ Whitelists attribute name=value pairs. """
    if _FILTER_FOR_FILTER_HTML_ATTRIBUTE.search(value):
        return value
    return "zSafehtmlz"

def _filter_element_name_helper(value):
    """ Whitelists HTML element names parts. """
    if _FILTER_FOR_FILTER_HTML_ELEMENT_NAME.search(value):
        return value
    return "zSafehtmlz"

# Matches all tags, HTML comments, and DOCTYPEs in tag soup HTML.
_HTML_TAG_REGEX = re.compile(
    r'(?i)<(?:!|/?[a-z])(?:[^>\x27"]|"[^"]*"|\x27[^\x27]*\x27)*>')

SANITIZER_FOR_ESC_MODE = [None for _ in xrange(0, _COUNT_OF_ESC_MODES)]
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_HTML] = escape_html
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_HTML_RCDATA] = escape_html_rcdata
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_HTML_ATTRIBUTE] = escape_html_attribute
SANITIZER_FOR_ESC_MODE[ESC_MODE_FILTER_HTML_ELEMENT_NAME] = (
    filter_html_element_name)
SANITIZER_FOR_ESC_MODE[ESC_MODE_FILTER_HTML_ATTRIBUTE] = filter_html_attribute
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_JS_STRING] = escape_js_string
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_JS_VALUE] = escape_js_value
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_JS_REGEX] = escape_js_regex
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_CSS_STRING] = escape_css_string
SANITIZER_FOR_ESC_MODE[ESC_MODE_FILTER_CSS_VALUE] = filter_css_value
SANITIZER_FOR_ESC_MODE[ESC_MODE_ESCAPE_URL] = escape_url
SANITIZER_FOR_ESC_MODE[ESC_MODE_NORMALIZE_URL] = normalize_url
SANITIZER_FOR_ESC_MODE[ESC_MODE_FILTER_URL] = filter_url
SANITIZER_FOR_ESC_MODE[ESC_MODE_ELIDE] = elide
SANITIZER_FOR_ESC_MODE[ESC_MODE_OPEN_QUOTE] = open_quote
