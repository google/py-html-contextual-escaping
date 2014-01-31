#!/usr/bin/env python -O

"""
Common definitions used by test files.
"""

ASCII_AND_SELECTED_CODEPOINTS = (
    u"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f"
    u"\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
    u" !\"#$%&'()*+,-./"
    u"0123456789:;<=>?"
    u"@ABCDEFGHIJKLMNO"
    u'PQRSTUVWXYZ[\\]^_'
    u"`abcdefghijklmno"
    u"pqrstuvwxyz{|}~\x7f"
    u"\u00A0\u0100\u2028\u2029\ufdec\ufeff\U0001D11E")
