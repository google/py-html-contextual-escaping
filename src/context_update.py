#!/usr/bin/python

"""
Defines the rules for propagating context across snippets of static template
content.
"""

from context import *
import debug
import escaping
import htmlentitydefs
import re


REGEX_PRECEDER_KEYWORDS = set([
    "break", "case", "continue", "delete", "do", "else", "finally",
    "instanceof", "return", "throw", "try", "typeof"])

def is_regex_preceder(js_tokens):
    """
    True iff a slash after the given run of non-whitespace tokens
    starts a regular expression instead of a div operator : (/ or /=).

    This fails on some valid but nonsensical JavaScript programs like
    x = ++/foo/i which is quite different than x++/foo/i, but is not known to
    fail on any known useful programs.
    It is based on the draft JavaScript 2.0 lexical grammar at
    (http://www.mozilla.org/js/language/js20-2000-07/rationale/syntax.html)
    and requires one token of lookbehind.

    js_tokens - A run of non-whitespace, non-comment, non string
    tokens not including the '/' character.  Non-empty.
    """

    # Tokens that precede a regular expression in JavaScript.
    # "!", "!=", "!==", "#", "%", "%=", "&", "&&",
    # "&&=", "&=", "(", "*", "*=", "+", "+=", ",",
    # "-", "-=", "->", ".", "..", "...", "/", "/=",
    # ":", "::", ";", "<", "<<", "<<=", "<=", "=",
    # "==", "===", ">", ">=", ">>", ">>=", ">>>",
    # ">>>=", "?", "@", "[", "^", "^=", "^^", "^^=",
    # "{", "|", "|=", "||", "||=", "~",
    # "break", "case", "continue", "delete", "do",
    # "else", "finally", "instanceof", "return",
    # "throw", "try", "typeof"

    js_tokens_len = len(js_tokens)
    last_char = js_tokens[-1]
    if last_char == '+' or last_char == '-':
        # ++ and -- are not
        sign_start = js_tokens_len - 1
        # Count the number of adjacent dashes or pluses.
        while sign_start > 0 and js_tokens[sign_start - 1] == last_char:
            sign_start -= 1
        num_adjacent = js_tokens_len - sign_start
        # True for odd numbers since "---" is the same as "-- -".
        # False for even numbers since "----" is the same as "-- --" which ends
        # with a decrement, not a minus sign.
        return (num_adjacent & 1) == 1
    elif last_char == '.':
        if js_tokens_len == 1:
            return True
        after_dot = js_tokens[-2]
        return not ("0" <= after_dot <= "9")
    elif last_char == '/':  # Match a div op, but not a regexp.
        return js_tokens_len <= 2
    else:
        # [:-?] matches ':', ';', '<', '=', '>', '?'
        # [{-~] matches '{', '|', '}', '~'
        if re.search(r'[#%&(*,:-?\[^{-~]', last_char):
            return True
        # Look for one of the keywords above.
        word = re.search(r'[\w$]+$', js_tokens)
        return (word and word.group(0)) in REGEX_PRECEDER_KEYWORDS


def context_union(context0, context1):
    """
    A context which is consistent with both contexts.  This should be
    used when multiple execution paths join, such as the path through
    the then-clause of an <code>{if}</code> command and the path
    through the else-clause.
    Returns STATE_ERROR when there is no such context consistent with both.
    """

    if context0 == context1:
        return context0

    if context0 == ((context1 & ~JS_CTX_ALL) | js_ctx_of(context0)):
        return (context0 & ~JS_CTX_ALL) | JS_CTX_UNKNOWN

    url_part_0 = url_part_of(context0)
    if context0 == ((context1 & ~URL_PART_ALL) | url_part_0):
        return (context0 & ~URL_PART_ALL) | URL_PART_UNKNOWN

    # Order by state so that we don't have to duplicate tests below.
    state0, state1 = state_of(context0), state_of(context1)
    if state0 > state1:
        context0, context1 = context1, context0
        state0, state1 = state1, state0

    # If we start in a tag name and end between attributes, then treat us as
    # between attributes.
    # This handles <b{if $bool} attrName="value"{/if}>.
    if state0 == STATE_TAG_NAME and state1 == STATE_TAG:
        # We do not need to compare element_type_of(a) and element_type_of(b)
        # since, in HTML_TAG_NAME, there is no tag name so no loss of
        # information.
        return context1

    if (state0 == STATE_TAG
        and element_type_of(context0) == element_type_of(context1)):
        # If one branch is waiting for an attribute name and the other is
        # waiting for an equal sign before an attribute value, then commit to
        # the view that the attribute name was a valueless attribute and
        # transition to a state waiting for another attribute name or the end
        # of a tag.
        if (state1 == STATE_ATTR_NAME
            # In an attribute value ended by a delimiter.
            or delim_type_of(context1) == DELIM_SPACE_OR_TAG_END):
            # TODO: do we need to require a space before any new attribute name?
            return context0

    return STATE_ERROR


def context_before_dynamic_value(context):
    """
    Some epsilon transitions need to be delayed until we get into a branch.
    For example, we do not transition into an unquoted attribute value
    context just because the raw text node that contained the "=" did
    not contain a quote character because the quote character may appear
    inside branches as in
        <a href={{if ...}}"..."{{else}}"..."{{/if}}>
    which was derived from production code.

    But we need to force epsilon transitions to happen consistentky before
    a dynamic value is considered as in
       <a href=${x}>
    where we consider $x as happening in an unquoted attribute value context,
    not as occuring before an attribute value.
    """
    state = state_of(context)
    if state == STATE_BEFORE_VALUE:
        context = context_after_attr_delimiter(
                element_type_of(context), attr_type_of(context),
                DELIM_SPACE_OR_TAG_END)
    return context


_PARTIAL_CONTEXT_FOR_ATTR = {
    ATTR_NONE: STATE_ATTR,
    # Start a JS block in a regex state since
    #   /foo/.test(str) && doSideEffect();
    # which starts with a regular expression literal is a valid and possibly
    # useful program, but there is no valid program which starts with a
    # division operator.
    ATTR_SCRIPT: STATE_JS | JS_CTX_REGEX,
    ATTR_STYLE: STATE_CSS,
    ATTR_URL: STATE_URL | URL_PART_NONE,
    }

def context_after_attr_delimiter(el_type, attr_type, delim):
    """
    Returns the context after an attribute delimiter for the given element
    type, attribute type, and delimiter type.
    """
    return _PARTIAL_CONTEXT_FOR_ATTR[attr_type] | el_type | delim


# Characters that break a line in JavaScript source suitable for use in a
# regex charset.
NLS = u"\r\n\u2028\u2029"


def _unescape_html(html):
    """
    Given HTML that would parse to a single text node, returns the text
    value of that node.
    """
    # Fast path for common case.
    if html.find("&") < 0:
        return html
    return re.sub(
        '&(?:#(?:x([0-9A-Fa-f]+)|([0-9]+))|([a-zA-Z0-9]+));',
        _decode_html_entity, html)


def _decode_html_entity(match):
    """
    Regex replacer that expects hex digits in group 1, or
    decimal digits in group 2, or a named entity in group 3.
    """
    group = match.group(1)
    if group:
        return unichr(int(group, 16))
    group = match.group(2)
    if group:
        return unichr(int(group, 10))
    group = match.group(3)
    if group:
        decoding = (
            htmlentitydefs.name2codepoint.get(group)
            # Try treating &GT; like &gt;.
            # This may be wrong for some codepoints.
            # Specifically, &Gt; and &Lt; which HTML5 adopted from MathML.
            # If htmlentitydefs is expanded to include mappings for those
            # entities, then this code will magically work.
            or htmlentitydefs.name2codepoint.get(group.lower()))
        if decoding is not None:
            return unichr(decoding)
    # Treat "&noSuchEntity;" as "&noSuchEntity;"
    return match.group(0)

def _end_of_attr_value(raw_text, delim):
    """
    Returns the end of the attribute value of -1 if delim indicates we are
    not in an attribute, or len(raw_text) if we are in an attribute but the
    end does not appear in raw_text.
    """
    if delim == DELIM_NONE:
        return -1
    if delim == DELIM_SPACE_OR_TAG_END:
        match = re.search(r'[\s>]', raw_text)
        if match:
            return match.start(0)
    else:
        quote = raw_text.find(DELIM_TEXT[delim])
        if quote >= 0:
            return quote
    return len(raw_text)


class _Transition(object):
    """
    Encapsulates a grammar production and the context after that
    production is seen in a chunk of HTML/CSS/JS input.
    """
    def __init__(self, pattern):
        self.pattern = re.compile(pattern)

    def is_applicable_to(self, prior, match):
        """
        True iff this transition can produce a context after the text in
        raw_text[0:match.start(0) + match.end(0)].
        This should not destructively modify the match.

        prior - The context prior to the token in match.
        match - The token matched by self.pattern.
        """
        return True

    def compute_next_context(self, prior, match):
        """
        Computes the context that this production transitions to after
        raw_text[0:match.start(0) + match.end(0)].

        prior - The context prior to the token in match.
        match - The token matched by self.pattern.

        Returns the context after the given token.
        """
        raise Exception("NOT IMPLEMENTED")

class _ToTransition(_Transition):
    """
    A transition to a given context.
    """

    def __init__(self, regex, dest):
        """dest - a context."""
        _Transition.__init__(self, regex)
        self.dest = dest

    def compute_next_context(self, prior, match):
        return self.dest

class _ToTagTransition(_Transition):
    """
    A transition to a context in the body of an open tag for the given
    element.
    """

    def __init__(self, regex, el_type):
        _Transition.__init__(self, regex)
        self.el_type = el_type

    def compute_next_context(self, prior, match):
        return STATE_TAG | self.el_type

_TAG_DONE_ELEMENT_TO_PARTIAL_CONTEXT = {
    ELEMENT_NONE: STATE_TEXT,
    ELEMENT_SCRIPT: STATE_JS | JS_CTX_REGEX,
    ELEMENT_STYLE: STATE_CSS,
    ELEMENT_LISTING: STATE_RCDATA,
    ELEMENT_TEXTAREA: STATE_RCDATA,
    ELEMENT_TITLE: STATE_RCDATA,
    ELEMENT_XMP: STATE_RCDATA,
    }

class _TagDoneTransition(_Transition):
    """
    Transitions from the end of a tag to the content-type appropriate to its
    body.
    """

    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        el_type = element_type_of(prior)
        return _TAG_DONE_ELEMENT_TO_PARTIAL_CONTEXT[el_type] | el_type

class _TransitionBackToTag(_Transition):
    """
    A transition back to a context in the body of an open tag.
    """

    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        return STATE_TAG | element_type_of(prior)

# Lower case names of attributes whose value is a URL.
# This does not identify attributes like "<meta content>" which is
# conditionally a URL
# depending on the value of other attributes.
# http://www.w3.org/TR/html4/index/attributes.html defines HTML4 attrs
# with type %URL.
_URL_ATTR_NAMES = set([
    "action",
    "archive",
    "background",
    "cite",
    "classid",
    "codebase",
    "data",
    "dsync",
    "formaction",
    "href",
    "longdesc",
    "manifest",
    "poster",
    "profile",
    "src",
    "usemap",
    "xmlns"])

class _TransitionToAttrName(_Transition):
    """
    A transition to a context in the name of an attribute whose attribute
    type is determined by its name seen thus far.
    """
    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        attr_name = match.group(1).lower()
        colon = attr_name.find(':')
        attr = attr_type_of(prior)
        if colon >= 0:
            if attr_name[:colon] == 'xmlns':
                attr = ATTR_URL
            # Treat html:href, xlink:href, svg:style, svg:onclick, etc. the
            # same regardless of prefix.
            # It is possible, but unlikely, that a non-malicious template
            # author would use a namespace that includes an XML variant where
            # foo:href is script, but barring that, this is a conservative
            # assumption.
            attr_name = attr_name[colon+1:]
        if attr_name.startswith("on"):
            attr = ATTR_SCRIPT
        elif "style" == attr_name:
            attr = ATTR_STYLE
        elif attr_name in _URL_ATTR_NAMES:
            attr = ATTR_URL
        # Heuristic for custom HTML attributes and HTML5 data-* attributes.
        elif (attr_name.find('url') & attr_name.find('uri')) >= 0:
            attr = ATTR_URL
        return STATE_ATTR_NAME | element_type_of(prior) | attr

class _TransitionToAttrValue(_Transition):
    """
    A transition to a context in the name of an attribute of the given type.
    """
    def __init__(self, regex, delim):
        _Transition.__init__(self, regex)
        self.delim = delim

    def compute_next_context(self, prior, match):
        return context_after_attr_delimiter(
            element_type_of(prior), attr_type_of(prior), self.delim)


class _TransitionToState(_Transition):
    """
    Transitions to a particular state.
    """
    
    def __init__(self, regex, state):
        """A transition to the given state."""
        _Transition.__init__(self, regex)
        self.state = state

    def compute_next_context(self, prior, match):
        return (prior & ~(URL_PART_ALL | STATE_ALL)) | self.state

class _TransitionToJsString(_Transition):
    """
    Transitions to a JS string state.
    """

    def __init__(self, regex, state):
        """A transition to the given state."""
        _Transition.__init__(self, regex)
        self.state = state

    def compute_next_context(self, prior, match):
        return (
            (prior & (ELEMENT_ALL | ATTR_ALL | DELIM_ALL))
            | self.state)

class _SlashTransition(_Transition):
    """
    Transitions into a regular expression literal or not depending on the
    JS context bits.
    """

    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        js_slash = js_ctx_of(prior)
        if js_slash == JS_CTX_DIV_OP:
            return ((prior & ~(STATE_ALL | JS_CTX_ALL))
                    | STATE_JS | JS_CTX_REGEX)
        elif js_slash == JS_CTX_REGEX:
            return ((prior & ~(STATE_ALL | JS_CTX_ALL))
                    | STATE_JSREGEXP | JS_CTX_NONE)
        else:
            raise Exception(
                ("Ambiguous / could be a RegExp or division.  " +
                 "Please add parentheses before `%s`") % match.group(0))

class _JsPuncTransition(_Transition):
    """
    Keeps JS context bits up-to-date.
    """

    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        if is_regex_preceder(match.group(0)):
            js_slash = JS_CTX_REGEX
        else:
            js_slash = JS_CTX_DIV_OP
        return (prior & ~JS_CTX_ALL) | js_slash

class _TransitionToSelf(_Transition):
    """A transition that consumes some content without changing state."""
    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        return prior

# Consumes the entire content without change if nothing else matched.
_TRANSITION_TO_SELF = _TransitionToSelf(r'$')
# Matching at the end is lowest possible precedence.

class _URLPartTransition(_Transition):
    """
    Inside a URL attribute value, keeps track of which part of a hierarchical
    URL we are in.
    """

    def __init__(self, pattern):
        _Transition.__init__(self, pattern)

    def compute_next_context(self, prior, match):
        url_part = url_part_of(prior)
        if url_part == URL_PART_NONE:
            url_part = URL_PART_PRE_QUERY

        if (url_part != URL_PART_QUERY_OR_FRAG
            # Matches '?', '#', or an encoded form thereof.
            and match.group(0)):
            url_part = URL_PART_QUERY_OR_FRAG
        return (prior & ~URL_PART_ALL) | url_part

_URL_PART_TRANSITION = _URLPartTransition(r'[?#]|$')
_CSSURL_PART_TRANSITION = _URLPartTransition(r'[?#]|\\(?:23|3[fF]|[?#])|$')


class _EndTagTransition(_Transition):
    """
    Transition when we see the start of an end tag like '</foo'.
    """

    def __init__(self, pattern):
        '''Matches the end of a special tag like "script".'''
        _Transition.__init__(self, pattern)

    # TODO: This transitions to an HTML_TAG state which accepts attributes.
    # So we allow nonsensical constructs like </br foo="bar">.
    # Add another HTML_END_TAG state that just accepts space and >.
    def compute_next_context(self, prior, match):
        return STATE_TAG | ELEMENT_NONE

    def is_applicable_to(self, prior, match):
        return attr_type_of(prior) == ATTR_NONE

_SCRIPT_TAG_END = _EndTagTransition(r'(?i)<\/script\b')
_STYLE_TAG_END = _EndTagTransition(r'(?i)<\/style\b')

_ELEMENT_TO_TAG_NAME = {
    ELEMENT_TEXTAREA: "textarea",
    ELEMENT_TITLE: "title",
    ELEMENT_LISTING: "listing",
    ELEMENT_XMP: "xmp",
    }

class _RcdataEndTagTransition(_Transition):
    """
    Transition that handles exit from tags like <title> and <textarea>
    which cannot contain tags.
    """
    
    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        return STATE_TAG | ELEMENT_NONE

    def is_applicable_to(self, prior, match):
        return (
            match.group(1).lower()
            == _ELEMENT_TO_TAG_NAME.get(element_type_of(prior)))

class _CssUriTransition(_Transition):
    """
    Handles transition into CSS url(...) constructs.
    """

    def __init__(self, regex):
        """
        Matches the beginning of a CSS URL with the delimiter, if any,
        in group 1.
        """
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        delim = match.group(1)
        if "\"" == delim:
            state = STATE_CSSDQ_URL
        elif "'" == delim:
            state = STATE_CSSSQ_URL
        else:
            state = STATE_CSS_URL
        return (prior & ~( STATE_ALL | URL_PART_ALL)) | state | URL_PART_NONE


class _DivPreceder(_Transition):
    """
    Matches a portion of JavaScript that can precede a division operator.
    """

    def __init__(self, regex):
        _Transition.__init__(self, regex)

    def compute_next_context(self, prior, match):
        return ((prior & ~(STATE_ALL | JS_CTX_ALL))
                | STATE_JS | JS_CTX_DIV_OP)

# For each state, a group of rules for consuming raw text and how that
# affects the document
# context.
# The rules each have an associated pattern, and the rule whose pattern
# matches earliest in the
# text wins.
_TRANSITIONS = [None for _ in xrange(0, COUNT_OF_STATES)]
_TRANSITIONS[STATE_TEXT] = (
    _TransitionToSelf( r"""^[^<]+""" ),
    _ToTransition( r"""<!--""", STATE_HTMLCMT ),
    _ToTagTransition( r"""(?i)<script(?=[\s>\/]|$)""", ELEMENT_SCRIPT ),
    _ToTagTransition( r"""(?i)<style(?=[\s>\/]|$)""", ELEMENT_STYLE ),
    _ToTagTransition( r"""(?i)<textarea(?=[\s>\/]|$)""",
                      ELEMENT_TEXTAREA ),
    _ToTagTransition( r"""(?i)<title(?=[\s>\/]|$)""", ELEMENT_TITLE ),
    _ToTagTransition( r"""(?i)<xmp(?=[\s>\/]|$)""", ELEMENT_XMP ),
    _ToTransition( r"""<""", STATE_HTML_BEFORE_TAG_NAME ),
    )
_TRANSITIONS[ STATE_RCDATA ] = (
    _RcdataEndTagTransition( r"""</(\w+)\b""" ),
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_HTML_BEFORE_TAG_NAME ] = (
    _ToTransition( r"""^[A-Za-z]+""", STATE_TAG_NAME ),
    _ToTransition( r"""^(?=[^A-Za-z])""", STATE_TEXT ),
    )
_TRANSITIONS[ STATE_TAG_NAME ] = (
    _TransitionToSelf( r"""^[A-Za-z0-9:-]*(?:[A-Za-z0-9]|$)""" ),
    _ToTagTransition( r"""^(?=[\/\s>])""", ELEMENT_NONE ),
    )
_TRANSITIONS[ STATE_TAG ] = (
    # Allows "data-foo" and other dashed attribute names, but
    # intentionally disallows "--" as an attribute name so that a tag ending
    # after a value-less attribute named "--" cannot be confused with a HTML
    # comment end ("-->").
    _TransitionToAttrName( r"""^\s*([A-Za-z][\w:-]*)""" ),
    _TagDoneTransition( r"""^\s*\/?>""" ),
    _TransitionToSelf( r"""^\s+$""" ),
    )
_TRANSITIONS[ STATE_ATTR_NAME ] = (
    _TransitionToSelf( r"""[\w-]+""" ),  # TODO: What does \w mean in python?
    # For a value-less attribute, make an epsilon transition back to the tag
    # body context to look for a tag end or another attribute name.
    _TransitionToState( r"""^""", STATE_AFTER_NAME ),
    )
_TRANSITIONS[ STATE_AFTER_NAME ] = (
    _TransitionToState( r"""^\s*=""", STATE_BEFORE_VALUE ),
    _TransitionToSelf( r"""^\s+""" ),
    _TransitionBackToTag( r"""^""" ),
    )
_TRANSITIONS[ STATE_BEFORE_VALUE ] = (
    _TransitionToAttrValue( r"""^\s*[\"]""", DELIM_DOUBLE_QUOTE ),
    _TransitionToAttrValue( r"""^\s*\'""", DELIM_SINGLE_QUOTE ),
    _TransitionToAttrValue( r"""^(?=[^\"\'\s>])""",  # Unquoted value start.
                           DELIM_SPACE_OR_TAG_END ),
    # Epsilon transition back if there is an empty value followed by an
    # obvious attribute name or a tag end.
    # The first branch handles the blank value in:
    #    <input value=>
    # and the second handles the blank value in:
    #    <input value= name=foo>
    _TransitionBackToTag( r"""^(?=>|\s+[\w-]+\s*=)""" ),
    _TransitionToSelf( r"""^\s+""" ),
    )
_TRANSITIONS[ STATE_HTMLCMT ] = (
    _ToTransition( r"""-->""", STATE_TEXT ),
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_ATTR ] = (
    _TRANSITION_TO_SELF,
    )
# The CSS transitions below are based on
# http://www.w3.org/TR/css3-syntax/#lexical
_TRANSITIONS[ STATE_CSS ] = (
    _TransitionToState( r"""\/\*""", STATE_CSSBLOCK_CMT ),
    _TransitionToState( r"""\/\/""", STATE_CSSLINE_CMT ),
    # TODO: Do we need to support non-standard but widely supported C++
    # style comments?
    _TransitionToState( r"""[\"]""", STATE_CSSDQ_STR ),
    _TransitionToState( r"""\'""", STATE_CSSSQ_STR ),
    _CssUriTransition( r"""(?i)\burl\s*\(\s*([\"\']?)""" ),
    _STYLE_TAG_END,
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_CSSBLOCK_CMT ] = (
    _TransitionToState( r"""\*\/""", STATE_CSS ),
    _STYLE_TAG_END,
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_CSSLINE_CMT ] = (
    _TransitionToState( r"""[\n\f\r]""", STATE_CSS ),
    _STYLE_TAG_END,
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_CSSDQ_STR ] = (
    _TransitionToState( r"""[\"]""", STATE_CSS ),
    # Line continuation or escape.
    _TransitionToSelf( r"""\\(?:\r\n?|[\n\f\"])""" ),
    _CSSURL_PART_TRANSITION,
    _ToTransition( r"""[\n\r\f]""", STATE_ERROR ),
    _STYLE_TAG_END,  # TODO: Make this an error transition?
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_CSSSQ_STR ] = (
    _TransitionToState( r"""\'""", STATE_CSS ),
    # Line continuation or escape.
    _TransitionToSelf( r"""\\(?:\r\n?|[\n\f\'])""" ),
    _CSSURL_PART_TRANSITION,
    _ToTransition( r"""[\n\r\f]""", STATE_ERROR ),
    _STYLE_TAG_END,  # TODO: Make this an error transition?
    )
_TRANSITIONS[ STATE_CSS_URL ] = (
    _TransitionToState( r"""[\\)\s]""", STATE_CSS ),
    _CSSURL_PART_TRANSITION,
    _TransitionToState( r"""[\"\']""", STATE_ERROR ),
    _STYLE_TAG_END,
    )
_TRANSITIONS[ STATE_CSSSQ_URL ] = (
    _TransitionToState( r"""\'""", STATE_CSS ),
    _CSSURL_PART_TRANSITION,
    # Line continuation or escape.
    _TransitionToSelf( r"""\\(?:\r\n?|[\n\f\'])""" ),
    _ToTransition( r"""[\n\r\f]""", STATE_ERROR ),
    _STYLE_TAG_END,
    )
_TRANSITIONS[ STATE_CSSDQ_URL ] = (
    _TransitionToState( r"""[\"]""", STATE_CSS ),
    _CSSURL_PART_TRANSITION,
    # Line continuation or escape.
    _TransitionToSelf( r"""\\(?:\r\n?|[\n\f\"])""" ),
    _ToTransition( r"""[\n\r\f]""", STATE_ERROR ),
    _STYLE_TAG_END,
    )
_TRANSITIONS[ STATE_JS ] = (
    _TransitionToState( r"""/[*]""", STATE_JSBLOCK_CMT ),
    _TransitionToState( r"""//""", STATE_JSLINE_CMT ),
    _TransitionToJsString( r"""[\"]""", STATE_JSDQ_STR ),
    _TransitionToJsString( r"""\'""", STATE_JSSQ_STR ),
    _SlashTransition( r"""/""" ),
    # Shuffle words, punctuation (besides /), and numbers off to an
    # analyzer which does a quick and dirty check to update
    # is_regex_preceder.
    _JsPuncTransition( r"""(?i)(?:[^<\/\"\'\s\\]|<(?!\/script))+""" ),
    _TransitionToSelf( r"""\s+""" ),  # Space
    _SCRIPT_TAG_END,
    )
_TRANSITIONS[ STATE_JSBLOCK_CMT ] = (
    _TransitionToState( r"""[*]/""", STATE_JS ),
    _SCRIPT_TAG_END,
    _TRANSITION_TO_SELF,
    )
# Line continuations are not allowed in line comments.
_TRANSITIONS[ STATE_JSLINE_CMT ] = (
    _TransitionToState( "[%s]" % NLS, STATE_JS ),
    _SCRIPT_TAG_END,
    _TRANSITION_TO_SELF,
    )
_TRANSITIONS[ STATE_JSDQ_STR ] = (
    _DivPreceder( r"""[\"]""" ),
    _SCRIPT_TAG_END,
    _TransitionToSelf(
        "(?i)" +                      # Case-insensitively
        "^(?:" +                      # from the start
            "[^\"\\\\" + NLS + "<]" + # match all but nls, quotes, \s, <;
            "|\\\\(?:" +              # or backslash followed by a
                "\\r\\n?" +           # line continuation
                "|[^\\r<]" +          # or an escape
                "|<(?!/script)" +     # or non-closing less-than.
            ")" +
            "|<(?!/script)" +
        ")+" ),
    )
_TRANSITIONS[ STATE_JSSQ_STR ] = (
    _DivPreceder( r"""\'""" ),
    _SCRIPT_TAG_END,
    _TransitionToSelf(
        "(?i)^(?:" +                   # Case-insensitively, from start
            "[^\'\\\\" + NLS + "<]" +  # match all but nls, quotes, \s, <;
            "|\\\\(?:" +               # or a backslash followed by a
                "\\r\\n?" +            # line continuation
                "|[^\\r<]" +           # or an escape;
                "|<(?!/script)" +      # or non-closing less-than.
            ")" +
            "|<(?!/script)" +
        ")+" ),
    )
_TRANSITIONS[ STATE_JSREGEXP ] = (
    _DivPreceder( r"""/""" ),
    _SCRIPT_TAG_END,
    _TransitionToSelf(
        "^(?:" +
            # We have to handle [...] style character sets specially since
            # in /[/]/, the second solidus doesn't end the RegExp.
            "[^\\[\\\\/<" + NLS + "]" + # A non-charset, non-escape token;
            "|\\\\[^" + NLS + "]" +     # an escape;
            "|\\\\?<(?!/script)" +
            "|\\[" +                    # or a character set containing
                "(?:[^\\]\\\\<" + NLS + "]" +  # normal characters,
                "|\\\\(?:[^" + NLS + "]))*" +  # and escapes;
                "|\\\\?<(?!/script)" +  # or non-closing angle less-than.
            "\\]" +
        ")+" ),
    )
    # TODO: Do we need to recognize URL attributes that start with
    # javascript:, data:text/html, etc. and transition to JS instead
    # with a second layer of percent decoding triggered by a protocol
    # in (DATA, JAVASCRIPT, NONE) added to Context?
_TRANSITIONS[ STATE_URL ] = ( _URL_PART_TRANSITION, )

_TRANSITIONS = tuple(_TRANSITIONS)


def _process_next_token(text, context):
    """
    Consume a portion of text and compute the next context.
    Output is stored in member variables.
    text - Non empty.

    Returns (n, context after text[:n])
    """

    if is_error_context(context):  # The ERROR state is infectious.
        return (len(text), context)

    # Find the transition whose pattern matches earliest
    # in the raw text.
    earliest_start = len(text)+1
    earliest_transition = None
    earliest_match = None

    for transition in _TRANSITIONS[state_of(context)]:
        match = transition.pattern.search(text)
        if not match:
            continue
        start = match.start(0)
        if (start < earliest_start
            and transition.is_applicable_to(context, match)):
            earliest_start = start
            earliest_transition = transition
            earliest_match = match

    if earliest_transition:
        num_consumed = earliest_match.end(0)
        next_context = earliest_transition.compute_next_context(
            context, earliest_match)
    else:
        num_consumed = len(text)
        next_context = STATE_ERROR

    if not num_consumed and state_of(next_context) == state_of(context):
        # Infinite loop.
        raise Exception('inf loop. for %r in %s'
                        % (text, debug.context_to_string(context)))

    return num_consumed, next_context


def process_raw_text(raw_text, context):
    """
    raw_text - A chunk of HTML/CSS/JS.
    context - The context before raw_text.

    Returns the context after raw_text.
    """

    while raw_text:
        # If we are in an attribute value, then decode raw_text (except
        # for the delimiter) up to the next occurrence of delimiter.

        # The end of the section to decode.  Either before a delimiter
        # or > symbol that closes an attribute, at the end of the raw_text,
        # or -1 if no decoding needs to happen.

        attr_value_end = _end_of_attr_value(raw_text, delim_type_of(context))
        if attr_value_end == -1:
            # Outside an attribute value.  No need to decode.
            num_consumed, context = _process_next_token(
                raw_text, context)
            raw_text = raw_text[num_consumed:]
        else:
            # Inside an attribute value.  Find the end and decode up to it.

            # All of the languages we deal with (HTML, CSS, and JS) use
            # quotes as delimiters.
            # When one language is embedded in the other, we need to
            # decode delimiters before trying to parse the content in the
            # embedded language.

            # For example, in
            #       <a onclick="alert(&quot;Hello {$world}&quot;)">
            # the decoded value of the event handler is
            #       alert("Hello {$world}")
            # so to determine the appropriate escaping convention we decode
            # the attribute value before delegating to _process_next_token.

            # We could take the cross-product of two languages to avoid
            # decoding but that leads to either an explosion in the
            # number of states, or the amount of lookahead required.

            # The end of the attribute value.  At attr_value_end, or
            # attr_value_end + 1 if a delimiter needs to be consumed.
            if attr_value_end < len(raw_text):
                attr_end = (
                    attr_value_end + len(DELIM_TEXT[delim_type_of(context)]))
            else:
                attr_end = -1

            # Decode so that the JavaScript rules work on attribute values
            # like
            #     <a onclick='alert(&quot;{$msg}!&quot;)'>

            # If we've already processed the tokens "<a", " onclick='" to
            # get into the single quoted JS attribute context, then we do
            # three things:
            #   (1) This class will decode "&quot;" to "\"" and work below
            #       to go from STATE_JS to STATE_JSDQ_STR.
            #   (2) Then the caller checks {$msg} and realizes that $msg is
            #       part of a JS string.
            #   (3) Then, the above will identify the "'" as the end, and
            #       so we reach here with:
            #       r a w T e x t = " ! & q u o t ; ) ' > "
            #                                         ^ ^
            #                            attr_value_end attr_end

            # We use this example more in the comments below.

            attr_value_tail = _unescape_html(raw_text[:attr_value_end])
            # attr_value_tail is "!\")" in the example above.

            # Recurse on the decoded value.
            while attr_value_tail:
                num_consumed, context = _process_next_token(
                    attr_value_tail, context)
                attr_value_tail = attr_value_tail[num_consumed:]

            # TODO: Maybe check that context is legal to end an attr in.
            # Throw if the attribute ends inside a quoted string.

            if attr_end != -1:
                raw_text = raw_text[attr_end:]
                # raw_text is now ">" from the example above.

                # When an attribute ends, we're back in the tag.
                context = STATE_TAG | element_type_of(context)
            else:
                # Whole tail is part of an unterminated attribute.
                if attr_value_end != len(raw_text):
                    raise Exception()  # Illegal state.
                raw_text = ""
    return context


# TODO: If we need to deal with untrusted templates, then we need to make
# sure that tokens like <!--, </script>, etc. are never split with empty
# strings.
# We could do this by walking all possible paths through each template
# (both branches for ifs, each case for switches, and the 0,1, and 2+
# iteration case for loops).
# For each template, tokenize the original's raw_text nodes using
# RawTextContextUpdater and then tokenize one single raw_text node made by
# concatenating all raw_text.
# If one contains a sensitive token, e.g. <!--/ and the other doesn't, then
# we have a potential splitting attack.
# That and disallow unquoted attributes, and be paranoid about prints
# especially in the TAG_NAME productions.



def escaping_mode_for_hole(context_before):
    """
    context_before - The input context before the substitution.

    Returns (context after, (escaping_modes...,))
    """
    context = context_before_dynamic_value(context_before)
    esc_mode0 = escaping.ESC_MODE_FOR_STATE.get(state_of(context))
    url_part = url_part_of(context)
    if url_part == URL_PART_NONE:
        esc_mode0 = escaping.ESC_MODE_FILTER_NORMALIZE_URL
        context = (context & ~URL_PART_ALL) | URL_PART_PRE_QUERY
    elif url_part == URL_PART_PRE_QUERY:
        esc_mode0 = escaping.ESC_MODE_FILTER_NORMALIZE_URL
        # TODO: CSS escaper when it's a CSS string literal.
    elif url_part == URL_PART_QUERY_OR_FRAG:
        esc_mode0 = escaping.ESC_MODE_ESCAPE_URL
    else:
        return STATE_ERROR  # Unknown URL part.

    if esc_mode0 is None:
        return STATE_ERROR

    esc_mode1 = None
    delim_type = delim_type_of(context)
    if delim_type != DELIM_NONE:
        # Figure out how to escape the attribute value.
        if esc_mode0 == escaping.ESC_MODE_ESCAPE_HTML_ATTRIBUTE:
            if delim_type == DELIM_SPACE_OR_TAG_END:
                esc_mode0 = escaping.ESC_MODE_ESCAPE_HTML_ATTRIBUTE_NOSPACE
        elif (esc_mode0 not in (escaping.ESC_MODE_ESCAPE_HTML,
                                escaping.ESC_MODE_ESCAPE_HTML_ATTRIBUTE_NOSPACE)
              and esc_mode0 not in escaping.HTML_EMBEDDABLE_ESC_MODES):
            if delim_type == DELIM_SPACE_OR_TAG_END:
                esc_mode1 = escaping.ESC_MODE_ESCAPE_HTML_ATTRIBUTE_NOSPACE
            else:
                esc_mode1 = escaping.ESC_MODE_ESCAPE_HTML_ATTRIBUTE
    if esc_mode1 is not None:
        return context, (esc_mode0, esc_mode1)
    else:
        return context, (esc_mode0,)