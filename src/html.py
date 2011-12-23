#!/usr/bin/python

"""
HTML5 definitions including a replacement for htmlentitydefs.
"""

import re

# Lower case names of attributes whose value is a URL.
# This does not identify attributes like "<meta content>" which is
# conditionally a URL
# depending on the value of other attributes.
# http://www.w3.org/TR/html4/index/attributes.html defines HTML4 attrs
# with type %URL.
URL_ATTR_NAMES = set([
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


def unescape_html(html):
    """
    Given HTML that would parse to a single text node, returns the text
    value of that node.
    """
    # Fast path for common case.
    if html.find("&") < 0:
        return html
    if not _ENTITY_NAME_TO_EXPANSION:
        _load_entities()
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
    return _ENTITY_NAME_TO_EXPANSION.get(
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


# Maps entity names (excluding & but including any ;) to codepoints.
# These are case-sensitive : unescape_html("&Gt;") != unescape_html("&gt;")
_ENTITY_NAME_TO_EXPANSION = {}

def _load_entities():
    """
    Loads entities from http://svn.whatwg.org/webapps/entities-unicode.inc
    and http://svn.whatwg.org/webapps/entities-legacy.inc
    """
    import os.path
    import sys
    for path_dir in sys.path:
        entity_file = os.path.join(path_dir, 'entities.inc')
        if os.path.exists(entity_file):
            in_file = open(entity_file, 'rb')
            try:
                entities_tab_delim = in_file.read()
            finally:
                in_file.close()
                in_file = None
            lines = entities_tab_delim.split('\n')
            for line in lines:
                if not line:
                    continue
                # A line is like "gt;\t3c", an entity name with ; if required
                # followed by a tab followed by one or more hex numbers
                # separated by tabs.
                records = line.split('\t')
                _ENTITY_NAME_TO_EXPANSION[records[0]] = ''.join(
                    [_unichr(int(record, 16)) for record in records[1:]])
            break
