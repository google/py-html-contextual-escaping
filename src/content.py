#!/usr/bin/py

"""
Defines non-plain text string wrappers.
"""

# A snippet of HTML that does not start or end inside a tag, comment, entity,
# or DOCTYPE; and that does not contain any executable code
# (JS, "<object>"s, etc.) from a different trust domain.
CONTENT_KIND_HTML = 0

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
CONTENT_KIND_JS_STR_CHARS = 1

# A properly encoded portion of a URL.
CONTENT_KIND_URL = 2

class TypedContent(object):
    """
    A wrapped string whose content is of a particular kind.
    For example, an instance's kind property might indicate that it is a string
    of HTML, not a string of plain text.
    """

    def __init__(self, content, kind):
        if type(content) not in (unicode, str):
            content = str(content)
        if type(kind) is not int:
            raise Exception(kind)
        self.content = content
        self.kind = kind

    def __str__(self):
        return self.content

class SafeHTML(TypedContent):
    """
    A string of HTML that can safely be embedded in
    a PCDATA context in your app.  If you would be surprised to find that an
    HTML sanitizer produced 's' (e.g. it runs code or fetches bad URLs)
    and you wouldn't write a template that produces 's' on security or
    privacy grounds, then don't pass 's' here.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_HTML)

class SafeJsStrChars(TypedContent):
    """
    A string of JS that when evaled, produces a
    value that does not depend on any sensitive data and has no side effects
    OR a string of JS that does not reference any variables or have
    any side effects not known statically to the app authors.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_JS_STR_CHARS)


class SafeURI(TypedContent):
    """
    A chunk of URL that the caller knows is safe to emit in a template.
    """

    def __init__(self, content):
        TypedContent.__init__(self, content, CONTENT_KIND_URL)
