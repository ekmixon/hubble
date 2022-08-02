# -*- coding: utf-8 -*-
"""
This is the default pcre matcher.
"""
import re


def match(tgt, opts=None):
    """
    Returns true if the passed pcre regex matches
    """
    return (
        bool(re.match(tgt, opts["id"]))
        if opts
        else bool(re.match(tgt, __opts__["id"]))
    )
