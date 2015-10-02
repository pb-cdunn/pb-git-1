#!/usr/bin/env python2.7
"""Run this in the directory of the submodule container.
"""
import os
import re
import shlex
import subprocess
import sys

def log(msg):
    sys.stderr.write(msg + '\n')
def system(call):
    log(call)
    rc = os.system(call)
    if rc:
        raise Exception('{rc} <- {call!r}'.format(rc=rc, call=call))
def capture(call):
    log('`{}`'.format(call))
    return subprocess.check_output(shlex.split(call))
"""
 5d527739295c82bf4a141532d61019b9d155cc99 DALIGNER (heads/master)
 3e2231218d94f1f2a9083ae5695fb0d888b3e405 FALCON (0.2JASM-261-g3e22312)
 64d08e363e88b9356b587f2524fdc299a61d0791 pith (remotes/origin/HEAD)
 ...
"""
def map_commits(listing):
    d = dict()
    re_lines = re.compile(r'\s*(?P<sha1>\w+)\s+(?P<name>\S+)')
    for mo in re_lines.finditer(listing):
        log(repr(mo.groups()))
        name, sha1 = mo.group('name', 'sha1')
        d[name] = sha1
    return d
def main(argv):
    listing = capture('git submodule')    
    log(listing)
    print map_commits(listing)

main(sys.argv)
