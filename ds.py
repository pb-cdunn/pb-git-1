#!/usr/bin/env python2.7
from contextlib import contextmanager
import argparse
import ConfigParser as configparser
import logging
import os
import pprint
import re
import shlex
import StringIO
import subprocess
import sys

logging.basicConfig()
log = logging.getLogger(__name__)

@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        yield
    finally:
        os.chdir(prevdir)
def system(call):
    log.info(call)
    rc = os.system(call)
    if rc:
        raise Exception('{rc} <- {call!r}'.format(rc=rc, call=call))
def gitmodules_as_config(content):
    re_initial_ws = re.compile('^\s*(.*)$', re.MULTILINE)
    config = re_initial_ws.sub(r'\1', content)
    log.info(config)
    return config

def init(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if args.verbose:
        logging.getLogger().setLevel(logging.NOTSET)
    directory = os.path.dirname(os.path.abspath(args.group_file))
    group = open(args.group_file).read()
    group = eval(group) # N.B. code injection
    if args.reformat_group_file:
        with open(args.group_file, 'w') as ifs:
            ifs.write(pprint.pformat(group) + '\n')
    log.info(args.func)
    log.info(args)
    log.info(repr(group['repos']))
    return group, directory
def prepend_section(fp, name='default'):
    content = fp.read()
    return StringIO.StringIO('[{name}]\n'.format(name=name) + content)
def get_ini(conf):
    fp = open(conf['ini'])
    sfp = prepend_section(fp)
    cp = configparser.ConfigParser()
    cp.readfp(sfp)
    log.info(cp.items('default'))
    return dict(cp.items('default'))
def get_sha1(ini):
    return ini['commit']
def mkdirs(d):
    if not os.path.isdir(d):
        log.info('mkdir -p {}'.format(d))
        os.makedirs(d)
def checkout_repo(conf):
    log.info(conf)
    d = conf['path']
    if not os.path.exists(d):
        parent = os.path.dirname(os.path.abspath(d))
        mkdirs(parent)
        with cd(parent):
            system('git clone {}'.format(conf['url']))
    ini = get_ini(conf)
    log.info(ini)
    sha1 = get_sha1(ini)
    with cd(d):
        system('git checkout {}'.format(sha1))
def checkout(args):
    group, directory = init(args)
    with cd(directory):
        # Directories are relative to the location of group_file, for now.
        for repo, repo_conf in group['repos'].iteritems():
            checkout_repo(repo_conf)
def capture(call):
    log.info('`{}`'.format(call))
    return subprocess.check_output(shlex.split(call))
"""
 5d527739295c82bf4a141532d61019b9d155cc99 DALIGNER (heads/master)
 3e2231218d94f1f2a9083ae5695fb0d888b3e405 FALCON (0.2JASM-261-g3e22312)
 64d08e363e88b9356b587f2524fdc299a61d0791 pith (remotes/origin/HEAD)
 ...
"""
def map_sha1s(listing):
    d = dict()
    re_lines = re.compile(r'\s*(?P<sha1>\w+)\s+(?P<name>\S+)')
    for mo in re_lines.finditer(listing):
        log.info(repr(mo.groups()))
        name, sha1 = mo.group('name', 'sha1')
        d[name] = sha1
    return d
def get_submodule_sha1s(d):
    with cd(d):
        listing = capture('git submodule')
        return map_sha1s(listing)
def write_repo_config(fp, cfg):
    section = 'general'
    cp = configparser.ConfigParser()
    if not cp.has_section(section):
        cp.add_section(section)
    for key, val in cfg.iteritems():
        cp.set(section, key, val)
    cp.write(fp)
def convert(args):
    init(args)
    log.info(args.gitmodules)
    group = dict()
    repos = dict()
    group['repos'] = repos
    # For now, require full path to '.gitmodules'.
    directory = os.path.dirname(os.path.abspath(args.gitmodules))
    fp = StringIO.StringIO(gitmodules_as_config(open(args.gitmodules).read()))
    cp = configparser.ConfigParser()
    cp.readfp(fp)
    re_name = re.compile(r'submodule "(.*)"')
    for sec in cp.sections():
        log.info(sec)
        name = re_name.search(sec).group(1)
        items = cp.items(sec)
        data = dict(items)
        repos[name] = data
    log.info(repr(repos))
    sha1s = get_submodule_sha1s(directory)
    assert sorted(sha1s.keys()) == sorted(repos.keys())
    for name, sha1 in sha1s.iteritems():
        repos[name]['sha1now'] = sha1
        repos[name]['sha1pre'] = sha1
    log.info(pprint.pformat(repos))
    os.rename(directory, directory + '.bak')
    mkdirs(directory)
    for name, cfg in repos.iteritems():
        fn = os.path.join(directory, '{}.ini'.format(name))
        log.info('Writing {}'.format(fn))
        with open(fn, 'w') as fp:
            write_repo_config(fp, cfg)
def main(argv):
    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--group-file',
            default='conf.py',
            help='File describing a group of modules')
    parser.add_argument('-v', '--verbose',
            action='store_true')
    parser.add_argument('-r', '--reformat-group-file',
            action='store_true',
            help='Canonicalize the group-file. Then proceed.')
    subparsers = parser.add_subparsers()
    p = subparsers.add_parser('checkout',
            #aliases=['co'],
            )
    p.set_defaults(func=checkout)
    p = subparsers.add_parser('convert',
            help='Convert .gitmodules to this system.',
            )
    p.add_argument('-g', '--gitmodules',
            help='Path to .gitmodules file')
    p.set_defaults(func=convert)
    args = parser.parse_args(argv[1:])
    args.func(args)

main(sys.argv)
