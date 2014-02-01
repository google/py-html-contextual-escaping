#!/usr/bin/py

"""
Defines non-plain text string wrappers.
"""

# text/plain
CONTENT_KIND_PLAIN = 0

# text/css
# A string in one of the CSS (stylesheet, rule, value) productions, or a
# semicolon separated list of CSS properties.
CONTENT_KIND_CSS = 1

# text/html
# A snippet of HTML that does not start or end inside a tag, comment, entity,
# or DOCTYPE; and that does not contain any executable code
# (JS, "<object>"s, etc.) from a different trust domain.
CONTENT_KIND_HTML = 2

# text/html
# An HTML attribute like name=value.
CONTENT_KIND_HTML_ATTR = 3

# text/javascript
# A JS expression, or SourceElement list.
CONTENT_KIND_JS = 4

# A sequence of code units that can appear between quotes (either kind) in a
# JS program without causing a parse error, and without causing any side
# effects.
#
# The content should not contain unescaped quotes, newlines, or anything else
# that would cause parsing to fail or to cause a JS parser to finish the
# string it's parsing inside the content.
#
# The content must also not end inside an escape sequence ; no partial octal
# escape sequences or odd number of '\\'s at the end.
CONTENT_KIND_JS_STR_CHARS = 5

# A properly encoded portion of a URL.
CONTENT_KIND_URL = 6


class TypedContent(object):
    """
    A wrapped string whose content is of a particular kind.
    For example, an instance's kind property might indicate that it is a string
    of HTML, not a string of plain text.
    """

    def __init__(self, content, kind):
        assert type(content) in (str, unicode)
        if type(kind) is not int:
            raise ValueError(kind)
        # The string content.
        self.content = content
        # Describes the context in which content is safe.
        self.kind = kind

    def __str__(self):
        return self.content


class SafeCSS(TypedContent):
    """
     CSS encapsulates known safe content that matches any of:
       1. The CSS3 stylesheet production, such as `p { color: purple }`.
       2. The CSS3 rule production, such as `a[href=~"https:"].foo#bar`.
       3. CSS3 declaration productions, such as `color: red; margin: 2px`.
       4. The CSS3 value production, such as `rgba(0, 0, 255, 127)`.
     See http://www.w3.org/TR/css3-syntax/#style
     """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_CSS)


class SafeHTML(TypedContent):
    """
    HTML encapsulates a known safe HTML document fragment.
    It should not be used for HTML from a third-party, or HTML with
    unclosed tags or comments. The outputs of a sound HTML sanitizer
    and a template escaped by this package are fine for use with HTML.

    If you would be surprised to find that an HTML sanitizer produced
    a string s (because it runs code or fetches bad URLs) and you
    wouldn't write a template that produces that string s on security or
    privacy grounds, then don't use s here.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_HTML)


class SafeHTMLAttr(TypedContent):
    """
    HTMLAttr encapsulates an HTML attribute from a trusted source,
    for example: ` dir="ltr"`.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_HTML_ATTR)


class SafeJS(TypedContent):
    """
    JS encapsulates a known safe EcmaScript5 Expression, or example,
    `(x + y * z())`. 
    Template authors are responsible for ensuring that typed expressions
    do not break the intended precedence and that there is no
    statement/expression ambiguity as when passing an expression like
    "{ foo: bar() }\n['foo']()", which is both a valid Expression and a
    valid Program with a very different meaning.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_JS)


class SafeJSStr(TypedContent):
    """
    JSStr encapsulates a sequence of characters meant to be embedded
    between quotes in a JavaScript expression.
    The string must match a series of StringCharacters:

        StringCharacter :: SourceCharacter but not `\` or LineTerminator
                         | EscapeSequence

    Note that LineContinuations are not allowed.
    SafeJSStr('foo\\nbar') is fine, but SafeJSStr('foo\\\nbar') is not.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_JS_STR_CHARS)


class SafeURL(TypedContent):
    """
    URL encapsulates a known safe URL as defined in RFC 3896.
    A URL like `javascript:checkThatFormNotEditedBeforeLeavingPage()`
    from a trusted source should go in the page, but by default dynamic
    `javascript:` URLs are filtered out since they are a frequently
    exploited injection vector.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_URL)
