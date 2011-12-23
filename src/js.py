#!/usr/bin/python

"""
Utilities for dealing with JavaScript source code.
"""

import context
import re


_REGEX_PRECEDER_KEYWORDS = set([
    "break", "case", "continue", "delete", "do", "else", "finally",
    "instanceof", "return", "throw", "try", "typeof"])

def next_js_ctx(js_tokens, ctx):
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

    js_tokens = js_tokens.strip()
    if not js_tokens:
        return ctx

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
        is_regex = (num_adjacent & 1) == 1
    elif last_char == '.':
        if js_tokens_len == 1:
            is_regex = True
        else:
            after_dot = js_tokens[-2]
            is_regex = not ("0" <= after_dot <= "9")
    elif last_char == '/':  # Match a div op, but not a regexp.
        is_regex = js_tokens_len <= 2
    elif re.search(r'[!#%&(*,:;<=>?\[^{|}~]', last_char):
        is_regex = True
    else:
        # Look for one of the keywords above.
        word = re.search(r'[\w$]+\Z', js_tokens)
        is_regex = (word and word.group(0)) in _REGEX_PRECEDER_KEYWORDS
    ctx = ctx & ~context.JS_CTX_ALL
    if is_regex:
        ctx = ctx | context.JS_CTX_REGEX
    else:
        ctx = ctx | context.JS_CTX_DIV_OP
    return ctx
