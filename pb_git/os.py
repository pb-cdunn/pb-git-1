from __future__ import absolute_import
import os

_timeout_exists = None

def system(call, timeout=None):
    """With timeout, if available.
    """
    global _timeout_exists
    if _timeout_exists is None:
        rc = os.system('timeout 1 true')
        _timeout_exists = not rc
    if timeout and _timeout_exists:
        call = 'timeout {} {}'.format(timeout, call)
    rc = os.system(call)
    if rc:
        print '{} <- "{}"'.format(rc, call)
    return rc
