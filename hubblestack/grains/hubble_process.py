# -*- coding: utf-8 -*-
'''
Set grains describing the hubble process.
'''


import os

# Import salt libs
import hubblestack.utils.platform

try:
    import pwd
except ImportError:
    import getpass
    pwd = None

try:
    import grp
except ImportError:
    grp = None


def _uid():
    '''
    Grain for the hubble User ID
    '''
    return None if hubblestack.utils.platform.is_windows() else os.getuid()


def _username():
    '''
    Grain for the hubble username
    '''
    return pwd.getpwuid(os.getuid()).pw_name if pwd else getpass.getuser()


def _gid():
    '''
    Grain for the hubble Group ID
    '''
    return None if hubblestack.utils.platform.is_windows() else os.getgid()


def _groupname():
    '''
    Grain for the hubble groupname
    '''
    if grp:
        try:
            groupname = grp.getgrgid(os.getgid()).gr_name
        except KeyError:
            groupname = ''
    else:
        groupname = ''

    return groupname


def _pid():
    return os.getpid()


def grains():
    ret = {
        'username': _username(),
        'groupname': _groupname(),
        'pid': _pid(),
    }

    if not hubblestack.utils.platform.is_windows():
        ret['gid'] = _gid()
        ret['uid'] = _uid()

    return ret
