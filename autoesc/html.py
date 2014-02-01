#!/usr/bin/env python -O

"""
HTML5 definitions including a replacement for htmlentitydefs.
"""

from autoesc import content
import re

CONTENT_KIND_UNSAFE = -1

# Maps lower-caseattribute names to a content type for the value of the given
# attribute.
# If an attribute affects (or can mask) the encoding or interpretation of
# other content, or affects the contents, idempotency, or credentials of a
# network message, then the value in this map is CONTENT_TYPE_UNSAFE.
# This map is derived from HTML5, specifically
# http://www.w3.org/TR/html5/Overview.html#attributes-1
# as well as "%URI"-typed attributes from
# http://www.w3.org/TR/html4/index/attributes.html
_ATTR_VALUE_TYPES = {
    "accept":          content.CONTENT_KIND_PLAIN,
    "accept-charset":  CONTENT_KIND_UNSAFE,
    "action":          content.CONTENT_KIND_URL,
    "alt":             content.CONTENT_KIND_PLAIN,
    "archive":         content.CONTENT_KIND_URL,
    "async":           CONTENT_KIND_UNSAFE,
    "attributename":   CONTENT_KIND_UNSAFE, # From <svg:set attributeName>.
    "autocomplete":    content.CONTENT_KIND_PLAIN,
    "autofocus":       content.CONTENT_KIND_PLAIN,
    "autoplay":        content.CONTENT_KIND_PLAIN,
    "background":      content.CONTENT_KIND_URL,
    "border":          content.CONTENT_KIND_PLAIN,
    "checked":         content.CONTENT_KIND_PLAIN,
    "cite":            content.CONTENT_KIND_URL,
    "challenge":       CONTENT_KIND_UNSAFE,
    "charset":         CONTENT_KIND_UNSAFE,
    "class":           content.CONTENT_KIND_PLAIN,
    "classid":         content.CONTENT_KIND_URL,
    "codebase":        content.CONTENT_KIND_URL,
    "cols":            content.CONTENT_KIND_PLAIN,
    "colspan":         content.CONTENT_KIND_PLAIN,
    "content":         CONTENT_KIND_UNSAFE,
    "contenteditable": content.CONTENT_KIND_PLAIN,
    "contextmenu":     content.CONTENT_KIND_PLAIN,
    "controls":        content.CONTENT_KIND_PLAIN,
    "coords":          content.CONTENT_KIND_PLAIN,
    "crossorigin":     CONTENT_KIND_UNSAFE,
    "data":            content.CONTENT_KIND_URL,
    "datetime":        content.CONTENT_KIND_PLAIN,
    "default":         content.CONTENT_KIND_PLAIN,
    "defer":           CONTENT_KIND_UNSAFE,
    "dir":             content.CONTENT_KIND_PLAIN,
    "dirname":         content.CONTENT_KIND_PLAIN,
    "disabled":        content.CONTENT_KIND_PLAIN,
    "draggable":       content.CONTENT_KIND_PLAIN,
    "dropzone":        content.CONTENT_KIND_PLAIN,
    "enctype":         CONTENT_KIND_UNSAFE,
    "for":             content.CONTENT_KIND_PLAIN,
    "form":            CONTENT_KIND_UNSAFE,
    "formaction":      content.CONTENT_KIND_URL,
    "formenctype":     CONTENT_KIND_UNSAFE,
    "formmethod":      CONTENT_KIND_UNSAFE,
    "formnovalidate":  CONTENT_KIND_UNSAFE,
    "formtarget":      content.CONTENT_KIND_PLAIN,
    "headers":         content.CONTENT_KIND_PLAIN,
    "height":          content.CONTENT_KIND_PLAIN,
    "hidden":          content.CONTENT_KIND_PLAIN,
    "high":            content.CONTENT_KIND_PLAIN,
    "href":            content.CONTENT_KIND_URL,
    "hreflang":        content.CONTENT_KIND_PLAIN,
    "http-equiv":      CONTENT_KIND_UNSAFE,
    "icon":            content.CONTENT_KIND_URL,
    "id":              content.CONTENT_KIND_PLAIN,
    "ismap":           content.CONTENT_KIND_PLAIN,
    "keytype":         CONTENT_KIND_UNSAFE,
    "kind":            content.CONTENT_KIND_PLAIN,
    "label":           content.CONTENT_KIND_PLAIN,
    "lang":            content.CONTENT_KIND_PLAIN,
    "language":        CONTENT_KIND_UNSAFE,
    "list":            content.CONTENT_KIND_PLAIN,
    "longdesc":        content.CONTENT_KIND_URL,
    "loop":            content.CONTENT_KIND_PLAIN,
    "low":             content.CONTENT_KIND_PLAIN,
    "manifest":        content.CONTENT_KIND_URL,
    "max":             content.CONTENT_KIND_PLAIN,
    "maxlength":       content.CONTENT_KIND_PLAIN,
    "media":           content.CONTENT_KIND_PLAIN,
    "mediagroup":      content.CONTENT_KIND_PLAIN,
    "method":          CONTENT_KIND_UNSAFE,
    "min":             content.CONTENT_KIND_PLAIN,
    "multiple":        content.CONTENT_KIND_PLAIN,
    "name":            content.CONTENT_KIND_PLAIN,
    "novalidate":      CONTENT_KIND_UNSAFE,
    # Skip handler names from
    # http://www.w3.org/TR/html5/Overview.html
    # #event-handlers-on-elements-document-objects-and-window-objects
    "open":            content.CONTENT_KIND_PLAIN,
    "optimum":         content.CONTENT_KIND_PLAIN,
    "pattern":         CONTENT_KIND_UNSAFE,
    "placeholder":     content.CONTENT_KIND_PLAIN,
    "poster":          content.CONTENT_KIND_URL,
    "profile":         content.CONTENT_KIND_URL,
    "preload":         content.CONTENT_KIND_PLAIN,
    "pubdate":         content.CONTENT_KIND_PLAIN,
    "radiogroup":      content.CONTENT_KIND_PLAIN,
    "readonly":        content.CONTENT_KIND_PLAIN,
    "rel":             CONTENT_KIND_UNSAFE,
    "required":        content.CONTENT_KIND_PLAIN,
    "reversed":        content.CONTENT_KIND_PLAIN,
    "rows":            content.CONTENT_KIND_PLAIN,
    "rowspan":         content.CONTENT_KIND_PLAIN,
    "sandbox":         CONTENT_KIND_UNSAFE,
    "spellcheck":      content.CONTENT_KIND_PLAIN,
    "scope":           content.CONTENT_KIND_PLAIN,
    "scoped":          content.CONTENT_KIND_PLAIN,
    "seamless":        content.CONTENT_KIND_PLAIN,
    "selected":        content.CONTENT_KIND_PLAIN,
    "shape":           content.CONTENT_KIND_PLAIN,
    "size":            content.CONTENT_KIND_PLAIN,
    "sizes":           content.CONTENT_KIND_PLAIN,
    "span":            content.CONTENT_KIND_PLAIN,
    "src":             content.CONTENT_KIND_URL,
    "srcdoc":          content.CONTENT_KIND_HTML,
    "srclang":         content.CONTENT_KIND_PLAIN,
    "start":           content.CONTENT_KIND_PLAIN,
    "step":            content.CONTENT_KIND_PLAIN,
    "style":           content.CONTENT_KIND_CSS,
    "tabindex":        content.CONTENT_KIND_PLAIN,
    "target":          content.CONTENT_KIND_PLAIN,
    "title":           content.CONTENT_KIND_PLAIN,
    "type":            CONTENT_KIND_UNSAFE,
    "usemap":          content.CONTENT_KIND_URL,
    "value":           CONTENT_KIND_UNSAFE,
    "width":           content.CONTENT_KIND_PLAIN,
    "wrap":            content.CONTENT_KIND_PLAIN,
    "xmlns":           content.CONTENT_KIND_URL,
    }

def attr_type(attr_name):
    """The content kind of the attribute with the given name."""

    attr_name = attr_name.lower()
    colon = attr_name.find(':')
    if colon >= 0:
        if attr_name[:colon] == 'xmlns':
            return content.CONTENT_KIND_URL
        # Treat html:href, xlink:href, svg:style, svg:onclick, etc. the
        # same regardless of prefix.
        # It is possible, but unlikely, that a non-malicious template
        # author would use a namespace that includes an XML variant where
        # foo:href is script, but barring that, this is a conservative
        # assumption.
        attr_name = attr_name[colon+1:]
    if attr_name.startswith("on"):
        return content.CONTENT_KIND_JS
    # Heuristic for custom HTML attributes and HTML5 data-* attributes.
    if (attr_name.find('url') & attr_name.find('uri')) >= 0:
        return content.CONTENT_KIND_URL
    typ = _ATTR_VALUE_TYPES.get(attr_name, None)
    if typ is not None:
        return typ
    if attr_name.startswith('data-'):
        return content.CONTENT_KIND_PLAIN
    return CONTENT_KIND_UNSAFE


ENTITY_NAME_TO_TEXT_ = None

def unescape_html(html):
    """
    Given HTML that would parse to a single text node, returns the text
    value of that node.
    """
    # Fast path for common case.
    if html.find("&") < 0:
        return html
    global ENTITY_NAME_TO_TEXT_
    if not ENTITY_NAME_TO_TEXT_:
        from autoesc import entities
        ENTITY_NAME_TO_TEXT_ = entities.ENTITY_NAME_TO_TEXT
    return re.sub(
        '&(?:#(?:[xX]([0-9A-Fa-f]+);|([0-9]+);)|([a-zA-Z0-9]+;?))',
        _decode_html_entity, html)


def _decode_html_entity(match):
    """
    Regex replacer that expects hex digits in group 1, or
    decimal digits in group 2, or a named entity in group 3.
    """
    group = match.group(1)
    if group:
        return _unichr(int(group, 16))
    group = match.group(2)
    if group:
        return _unichr(int(group, 10))
    group = match.group(3)
    return ENTITY_NAME_TO_TEXT_.get(
        group,
        # Treat "&noSuchEntity;" as "&noSuchEntity;"
        match.group(0))


def _unichr(codepoint):
    """Like unichr but works with supplemental codepoints."""
    if codepoint < 0x80:
        return chr(codepoint)
    elif codepoint < 0x10000:
        return unichr(codepoint)
    # Decode per UTF-16 spec.
    codepoint -= 0x10000
    return '%s%s' % (
        unichr(0xd800 | (codepoint >> 10)),
        unichr(0xdc00 | (codepoint & 0x3ff)))
