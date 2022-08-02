# -*- encoding: utf-8 -*-
"""
File-Permission type comparator used to match File permissions

Comparators are used by Audit module to compare module output
with the expected result
In FDG-connector, comparators might also be used with FDG

File-Permission comparator exposes various commands:

- "match"
    To match file permission values

    comparator:
        type: file_permission
        match:
            required_value: 644
            allow_more_strict: true

If allow_more_strict=False, exact file permission will be matched
If allow_more_strict=True, file permissions can be same or more strict
default value of allow_more_strict is False
"""
import logging

log = logging.getLogger(__name__)


def match(audit_id, result_to_compare, args):
    """
    Match File permissions

    :param result_to_compare:
        The value to compare. Example: 644
    :param args:
        Comparator dictionary as mentioned in the check.
    """
    log.debug('Running file_permission::match for audit_id: {0}'.format(audit_id))

    errors = []
    allow_more_strict = args['match'].get('allow_more_strict', False)
    if not isinstance(allow_more_strict, bool):
        allow_more_strict = False
    given_permission = str(result_to_compare)
    if given_permission != '0':
        given_permission = given_permission[1:]

    if ret_status := _check_mode(
        str(args['match']['required_value']),
        given_permission,
        allow_more_strict,
    ):
        return True, "File permission check passed"

    error_msg = 'File permission check failed. allow_more_strict={0}, Expected={1}, Got={2}'.format(
        allow_more_strict, args['match']['required_value'], given_permission)
    return False, error_msg


def _check_mode(max_permission, given_permission, allow_more_strict):
    """
    Checks whether a file's permission are equal to a given permission or more restrictive.
    Permission is a string of 3 digits [0-7]. 'given_permission' is the actual permission on file,
    'max_permission' is the expected permission on this file. Set 'allow_more_strict' to True,
    to allow more restrictive permissions as well. Example:

    _check_mode('644', '644', False)        returns         True
    _check_mode('644', '600', False)        returns         False
    _check_mode('644', '644', True)         returns         True
    _check_mode('644', '600', True)         returns         True
    _check_mode('644', '655', True)        returns         False

    """

    if given_permission == '0':
        return True

    if not allow_more_strict or max_permission == 'None':
        return max_permission == given_permission

    return bool(
        (
            _is_permission_in_limit(max_permission[0], given_permission[0])
            and _is_permission_in_limit(max_permission[1], given_permission[1])
            and _is_permission_in_limit(max_permission[2], given_permission[2])
        )
    )


def _is_permission_in_limit(max_permission, given_permission):
    """
    Return true only if given_permission is not more lenient that max_permission. In other words, if
    r or w or x is present in given_permission but absent in max_permission, it should return False
    Takes input two integer values from 0 to 7.
    """
    max_permission = int(max_permission)
    given_permission = int(given_permission)
    allowed_r = False
    allowed_w = False
    given_r = False
    given_w = False
    if max_permission >= 4:
        allowed_r = True
        max_permission -= 4
    if max_permission >= 2:
        allowed_w = True
        max_permission -= 2
    if given_permission >= 4:
        given_r = True
        given_permission -= 4
    if given_permission >= 2:
        given_w = True
        given_permission -= 2
    given_x = given_permission >= 1
    if given_r and (not allowed_r):
        return False
    allowed_x = max_permission >= 1
    return False if given_w and (not allowed_w) else not given_x or allowed_x
