# -*- encoding: utf-8 -*-
"""
String type comparator used to match Strings

Comparators are used by Audit module to compare module output
with the expected result
In FDG-connector, comparators might also be used with FDG

String comparator exposes various commands:

- "match"

    comparator:
        type: string
        match: '^root'
        is_regex: true # Optional, default False
        is_multiline: true # Optional, default=True. Works only when is_regex=True

- "match_any"

    comparator:
        type: string
        match_any:
            - '^root'
            - 'shadow'
        is_regex: true # Optional, default False
        is_multiline: false # Optional. Works only when is_regex=True
"""
import logging
import re

log = logging.getLogger(__name__)


def match(audit_id, result_to_compare, args):
    """
    Match String

    :param result_to_compare:
        The value to compare.
    :param args:
        Comparator dictionary as mentioned in the check.
    """
    log.debug('Running string::match for check: {0}'.format(audit_id))

    if _compare(result_to_compare, str(args['match']), args):
        return True, "Check Passed"
    return False, "string::match failure. Expected={0} Got={1}".format(result_to_compare, str(args['match']))


def match_any(audit_id, result_to_compare, args):
    """
    Match list of strings

    :param result_to_compare:
        The value to compare.
    :param args:
        Comparator dictionary as mentioned in the check.
    """
    log.debug('Running string::match_any for check: {0}'.format(audit_id))

    for option_to_match in args['match_any']:
        if _compare(result_to_compare, option_to_match, args):
            return True, "Check passed"

    # did not match
    return False, "string::match_any failure. Could not find {0} in list: {1}".format(result_to_compare,
                                                                                      str(args['match_any']))


def _compare(result_to_compare, expected_string, args):
    """
    Compare two strings, by processing different options
        (is_regex)
    """

    if not (is_regex := args.get('is_regex', False)):
        return result_to_compare == expected_string
    if is_multiline := args.get('is_multiline', True):
        return re.search(expected_string, result_to_compare, re.MULTILINE)
    return re.search(expected_string, result_to_compare)
