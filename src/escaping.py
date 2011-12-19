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

# Encodes HTML special characters and spaces so that the value can
# appear as part of an unquoted attribute.
ESC_MODE_ESCAPE_HTML_ATTRIBUTE_NOSPACE = 3

# Only allow a valid identifier - letters, numbers, dashes, and underscores.
# Throws an exception otherwise.
ESC_MODE_FILTER_HTML_ELEMENT_NAME = 4

# Only allow a valid identifier - letters, numbers, dashes, and underscores.
# Throws an exception otherwise.
ESC_MODE_FILTER_HTML_ATTRIBUTE = 5

# Encode all HTML special characters and quotes, and JS newlines as
# if to allow them to appear literally in a JS string.
ESC_MODE_ESCAPE_JS_STRING = 6

# If a number or boolean, output as a JS literal.  Otherwise surround
# in quotes and escape.  Make sure all HTML and space characters are
# quoted.
ESC_MODE_ESCAPE_JS_VALUE = 7

# Like ESC_MODE_ESCAPE_JS_STRING but additionally escapes RegExp specials like
# ".+*?$^[](){}".
ESC_MODE_ESCAPE_JS_REGEX = 8

# Must escape all quotes, newlines, and the close parenthesis using
# '\\' followed by hex followed by a space.
ESC_MODE_ESCAPE_CSS_STRING = 9

# If the value is numeric, renders it as a numeric value so that
# "{$n}px" works as expected, otherwise if it is a valid
# CSS identifier, outputs it without escaping, otherwise surrounds in
# quotes and escapes like ESC_MODE_ESCAPE_CSS_STRING.
ESC_MODE_FILTER_CSS_VALUE = 10

# Percent encode all URL special characters and characters that
# cannot appear unescaped in a URL such as spaces.  Make sure to
# encode pluses and parentheses.
# This corresponds to the JavaScript function encodeURIComponent.
ESC_MODE_ESCAPE_URL = 11

# Percent encode non-URL characters that cannot appear unescaped in a
# URL such as spaces, and encode characters that are not special in
# URIs that are special in languages that URIs are embedded in such
# as parentheses and quotes.  This corresponds to the JavaScript
# function encodeURI but additionally encodes quotes
# parentheses, and percent signs that are not followed by two hex
# digits.
ESC_MODE_NORMALIZE_URL = 12

# Like ESC_MODE_NORMALIZE_URL, but filters out schemes like "javascript:"
# that load code.
ESC_MODE_FILTER_NORMALIZE_URL = 13

# The explicit rejection of escaping.
ESC_MODE_NO_AUTOESCAPE = 14

# One greater than the max of ESC_MODE_*.
_COUNT_OF_ESC_MODES = 15

HTML_EMBEDDABLE_ESC_MODES = set([
    ESC_MODE_ESCAPE_HTML,
    ESC_MODE_ESCAPE_HTML_RCDATA,
    ESC_MODE_ESCAPE_HTML_ATTRIBUTE,
    ESC_MODE_ESCAPE_HTML_ATTRIBUTE_NOSPACE,
    ESC_MODE_FILTER_HTML_ELEMENT_NAME,
    ESC_MODE_FILTER_HTML_ATTRIBUTE,
    ESC_MODE_ESCAPE_CSS_STRING,
    ESC_MODE_ESCAPE_URL])


CONTENT_KIND_FOR_ESC_MODE = [None for _ in xrange(0, _COUNT_OF_ESC_MODES)]
CONTENT_KIND_FOR_ESC_MODE[ESC_MODE_ESCAPE_HTML] = content.CONTENT_KIND_HTML
CONTENT_KIND_FOR_ESC_MODE[ESC_MODE_ESCAPE_JS_STRING] = (
    content.CONTENT_KIND_JS_STR_CHARS)
CONTENT_KIND_FOR_ESC_MODE[ESC_MODE_NORMALIZE_URL] = content.CONTENT_KIND_URL
CONTENT_KIND_FOR_ESC_MODE[ESC_MODE_ESCAPE_URL] = content.CONTENT_KIND_URL
CONTENT_KIND_FOR_ESC_MODE[ESC_MODE_FILTER_NORMALIZE_URL] = (
    content.CONTENT_KIND_URL)

ESC_MODE_FOR_STATE = [None for _ in xrange(0, context.COUNT_OF_STATES)]
ESC_MODE_FOR_STATE[context.STATE_TEXT] = ESC_MODE_ESCAPE_HTML
ESC_MODE_FOR_STATE[context.STATE_RCDATA] = ESC_MODE_ESCAPE_HTML_RCDATA
ESC_MODE_FOR_STATE[context.STATE_HTML_BEFORE_TAG_NAME] = (
    ESC_MODE_FILTER_HTML_ELEMENT_NAME)
ESC_MODE_FOR_STATE[context.STATE_TAG_NAME] = ESC_MODE_FILTER_HTML_ELEMENT_NAME
ESC_MODE_FOR_STATE[context.STATE_TAG] = ESC_MODE_FILTER_HTML_ATTRIBUTE
ESC_MODE_FOR_STATE[context.STATE_ATTR_NAME] = ESC_MODE_FILTER_HTML_ATTRIBUTE
ESC_MODE_FOR_STATE[context.STATE_ATTR] = ESC_MODE_ESCAPE_HTML_ATTRIBUTE
ESC_MODE_FOR_STATE[context.STATE_CSS] = ESC_MODE_FILTER_CSS_VALUE
ESC_MODE_FOR_STATE[context.STATE_CSSDQ_STR] = ESC_MODE_ESCAPE_CSS_STRING
ESC_MODE_FOR_STATE[context.STATE_CSSSQ_STR] = ESC_MODE_ESCAPE_CSS_STRING
ESC_MODE_FOR_STATE[context.STATE_CSS_URL] = ESC_MODE_NORMALIZE_URL
ESC_MODE_FOR_STATE[context.STATE_CSSDQ_URL] = ESC_MODE_NORMALIZE_URL
ESC_MODE_FOR_STATE[context.STATE_CSSSQ_URL] = ESC_MODE_NORMALIZE_URL
ESC_MODE_FOR_STATE[context.STATE_JS] = ESC_MODE_ESCAPE_JS_VALUE
ESC_MODE_FOR_STATE[context.STATE_JSDQ_STR] = ESC_MODE_ESCAPE_JS_STRING
ESC_MODE_FOR_STATE[context.STATE_JSSQ_STR] = ESC_MODE_ESCAPE_JS_STRING
ESC_MODE_FOR_STATE[context.STATE_JSREGEXP] = ESC_MODE_ESCAPE_JS_REGEX
ESC_MODE_FOR_STATE[context.STATE_URL] = ESC_MODE_ESCAPE_HTML_ATTRIBUTE



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


def escape_html_attribute_nospace(value):
    """
    Escapes HTML special characters in a string including space and other
    characters that can end an unquoted HTML attribute value.

    value - The HTML to be escaped.  May not be a string, but the
        value will be coerced to a string.

    Returns an escaped version of value.
    """
    if (isinstance(value, content.TypedContent)
        and value.kind == content.CONTENT_KIND_HTML):
        return _normalize_html_nospace_helper(_strip_html_tags(value.content))
    if type(value) not in (str, unicode):
        value = str(value)
    return _escape_html_nospace_helper(value)


def filter_html_attribute(value):
    """
    Filters out strings that cannot be a substring of a valid HTML attribute.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a valid HTML attribute name part or name/value pair.
    \"zSafehtmlz\" if the input is invalid.
    """

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
        return value.content
    if type(value) not in (str, unicode):
        value = str(value)
    return _escape_js_string_helper(value)


def escape_js_value(value):
    """
    Encodes a value as a JavaScript literal.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a JavaScript code representation of the input.
    """

    escaped = json.dumps(
        value,
        ensure_ascii=True,  # Encodes JS newlines U+2028 and U+2029
        check_circular=True,  # Don't allow denial of service via cyclic vals.
        allow_nan=True,  # NaN is ok in JS.
        indent=None,
        default=lambda obj: obj.to_json())
    # Could provide default(obj) to convert user-defined classes to dicts.

    if not len(escaped):  # Paranoia.
        return " null "
    char0 = escaped[0]
    if char0 == '{':
        # There is a higher risk that {...} will be interpreted as a block than
        # that the parentheses will introduce a function call.
        escaped = '(%s)' % escaped
    elif char0 != '[':
        # "true" -> " true "
        # We surround values with spaces so that they can't be interpolated into
        # identifiers by accident.
        # We could use parentheses but those might be interpreted as a function
        # call.
        escaped = ' %s ' % escaped
    return escaped


def escape_js_regex(value):
    """
    Escapes characters in the string to make it valid content for a JS regular
    expression literal.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """
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

def escape_uri(value):
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
        return normalize_uri(value.content)
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

def normalize_uri(value):
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


def filter_normalize_uri(value):
    """
    Vets a URL's protocol and removes rough edges from a URL by escaping
    any raw HTML/JS string delimiters.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """

    if value is None:
        value = ""
    elif type(value) not in (str, unicode):
        value = str(value)
    if not _FILTER_FOR_FILTER_NORMALIZE_URL.match(value):
        return "#zSafehtmlz"
    return normalize_uri(value)


def escape_css_string(value):
    """
    Escapes a string so it can safely be included inside a quoted CSS string.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns an escaped version of value.
    """
    return _escape_css_string_helper(value)


def filter_css_value(value):
    """
    Encodes a value as a CSS identifier part, keyword, or quantity.

    value - The value to escape.  May not be a string, but the value
        will be coerced to a string.

    Returns a safe CSS identifier part, keyword, or quanitity.
    """

    if value is None:
        value = ""
    elif type(value) not in (str, unicode):
        value = str(value)
    return _filter_css_value_helper(value)


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
    "\/": "\\\/",
    "\\": "\\\\",
    }

def _replacer_for_js(match):
    """A regex replacer."""
    group = match.group(0)
    encoded = _ESCAPE_MAP_FOR_ESCAPE_JS_STRING__AND__ESCAPE_JS_REGEX.get(group)
    if encoded is None:
        # "\u2028" -> "\\u2028"
        encoded = r'\u%04x' % ord(group)
        _ESCAPE_MAP_FOR_ESCAPE_JS_STRING__AND__ESCAPE_JS_REGEX[group] = encoded
    return encoded

_ESCAPE_MAP_FOR_ESCAPE_CSS_STRING = {}

def _replacer_for_css(match):
    """A regexp replacer."""
    group = match.group(0)
    encoded = _ESCAPE_MAP_FOR_ESCAPE_CSS_STRING.get(group)
    if encoded is None:
        encoded = r'\%x ' % ord(group)
        _ESCAPE_MAP_FOR_ESCAPE_CSS_STRING[group] = encoded
    return encoded


_MATCHER_FOR_ESCAPE_HTML = re.compile(r'[\x00"&\x27<>]')

_MATCHER_FOR_NORMALIZE_HTML = re.compile(r'[\x00"\x27<>]')

_MATCHER_FOR_ESCAPE_HTML_NOSPACE = re.compile(
    r'[\x00\x09-\x0d "&\x27\-\/<->`\x85\xa0\u2028\u2029]')

_MATCHER_FOR_NORMALIZE_HTML_NOSPACE = re.compile(
    r'[\x00\x09-\x0d "\x27\-\/<->`\x85\xa0\u2028\u2029]')

_MATCHER_FOR_ESCAPE_JS_STRING = re.compile(
    r'[\x00\x08-\x0d"&\x27\/<->\\\x85\u2028\u2029]')

_MATCHER_FOR_ESCAPE_JS_REGEX = re.compile(
    r'[\x00\x08-\x0d"$&-\/:<-?\[-^\x7b-\x7d\x85\u2028\u2029]')

_MATCHER_FOR_ESCAPE_CSS_STRING = re.compile(
    r'[\x00\x08-\x0d"&-*\/:->@\\\x7b\x7d\x85\xa0\u2028\u2029]')

_FILTER_FOR_FILTER_CSS_VALUE = re.compile(
    r'(?i)^(?!-*(?:expression|(?:moz-)?binding))'
    r'(?:[.#]?-?(?:[_a-z0-9][_a-z0-9-]*)'
    r'(?:-[_a-z][_a-z0-9-]*)*-?|-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9])'
    r'(?:[a-z]{1,2}|%)?|!important|)$')

_FILTER_FOR_FILTER_NORMALIZE_URL = re.compile(
    r'(?i)^(?:(?:https?|mailto):|[^&:\/?#]*(?:[\/?#]|$))')

_FILTER_FOR_FILTER_HTML_ATTRIBUTE = re.compile(
    r'(?i)^(?!style|on|action|archive|background|cite|classid|codebase|data'
    r'|dsync|href|longdesc|src|usemap)(?:[a-z0-9_$:-]*|dir=(?:ltr|rtl))$')

_FILTER_FOR_FILTER_HTML_ELEMENT_NAME = re.compile(
    r'(?i)^(?!script|style|title|textarea|xmp|no)[a-z0-9_$:-]*$')

def _escape_html_helper(value):
    """ '<a&gt;' -> '&lt;a&amp;gt;' """
    return _MATCHER_FOR_ESCAPE_HTML.sub(_replacer_for_html, value)

def _normalize_html_helper(value):
    """ '<a&gt;' -> '&lt;a&gt;' """
    return _MATCHER_FOR_NORMALIZE_HTML.sub(_replacer_for_html, value)

def _escape_html_nospace_helper(value):
    """ '<a &gt;' -> '&lt;a&#32;&amp;gt;' """
    return _MATCHER_FOR_ESCAPE_HTML_NOSPACE.sub(_replacer_for_html, value)

def _normalize_html_nospace_helper(value):
    """ '<a &gt;' -> '&lt;a&#32;&gt;' """
    return _MATCHER_FOR_NORMALIZE_HTML_NOSPACE.sub(_replacer_for_html, value)

def _escape_js_string_helper(value):
    """ '</script>' -> '\x3c/script\x3e' """
    return _MATCHER_FOR_ESCAPE_JS_STRING.sub(_replacer_for_js, value)

def _escape_js_regex_helper(value):
    """ '</script>' -> '\x3c\x2fscript\x3e' """
    return _MATCHER_FOR_ESCAPE_JS_REGEX.sub(_replacer_for_js, value)

def _escape_css_string_helper(value):
    """ '</style>' -> '\3c \2f style\3e ' """
    return _MATCHER_FOR_ESCAPE_CSS_STRING.sub(_replacer_for_css, value)

def _filter_css_value_helper(value):
    """ Blocks certain kinds of CSS token boundaries. """
    if _FILTER_FOR_FILTER_CSS_VALUE.search(value):
        return value
    return "zSafehtmlz"

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
    r'(?i)<(?:!|\/?[a-z])(?:[^>\x27"]|"[^"]*"|\x27[^\x27]*\x27)*>')

SANITIZER_FOR_ESC_MODE = [None for _ in xrange(0, _COUNT_OF_ESC_MODES)]
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_HTML ] = escape_html
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_HTML_RCDATA ] = escape_html_rcdata
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_HTML_ATTRIBUTE ] = escape_html_attribute
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_HTML_ATTRIBUTE_NOSPACE ] = (
    escape_html_attribute_nospace)
SANITIZER_FOR_ESC_MODE[ ESC_MODE_FILTER_HTML_ELEMENT_NAME ] = (
    filter_html_element_name)
SANITIZER_FOR_ESC_MODE[ ESC_MODE_FILTER_HTML_ATTRIBUTE ] = filter_html_attribute
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_JS_STRING ] = escape_js_string
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_JS_VALUE ] = escape_js_value
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_JS_REGEX ] = escape_js_regex
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_CSS_STRING ] = escape_css_string
SANITIZER_FOR_ESC_MODE[ ESC_MODE_FILTER_CSS_VALUE ] = filter_css_value
SANITIZER_FOR_ESC_MODE[ ESC_MODE_ESCAPE_URL ] = escape_uri
SANITIZER_FOR_ESC_MODE[ ESC_MODE_NORMALIZE_URL ] = normalize_uri
SANITIZER_FOR_ESC_MODE[ ESC_MODE_FILTER_NORMALIZE_URL ] = filter_normalize_uri
