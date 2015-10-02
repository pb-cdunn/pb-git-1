#!/usr/bin/env python2.7
"""
We use a separate file for each module b/c that makes them easier to
update in p4.
"""
from contextlib import contextmanager
import argparse
import ConfigParser as configparser
import glob
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
def capture(call):
    log.info('`{}`'.format(call))
    return subprocess.check_output(shlex.split(call))
def rename(old, new):
    log.info('Moving "{}" to "{}"'.format(old, new))
    os.rename(old, new)
def init(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if args.verbose:
        logging.getLogger().setLevel(logging.NOTSET)
def mkdirs(d):
    if not os.path.isdir(d):
        log.info('mkdir -p {}'.format(d))
        os.makedirs(d)
def write_repo_config(fp, cfg, section='general'):
    """Write dict 'cfg' into section of ConfigParser file.
    """
    cp = configparser.ConfigParser()
    if not cp.has_section(section):
        cp.add_section(section)
    for key, val in cfg.iteritems():
        cp.set(section, key, val)
    cp.write(fp)
def read_repo_config(fp, section='general'):
    """Return dict.
    Opposite of write_repo_config().
    """
    cp = configparser.ConfigParser()
    cp.readfp(fp)
    return dict(cp.items(section))
def read_modules():
    """Read all .ini from cwd.
    Return dict(name: config).
    """
    repos = dict()
    for fn in glob.glob('*.ini'):
        log.info(fn)
        cfg = read_repo_config(open(fn))
        log.debug(cfg)
        name = fn[:-4]
        repos[name] = cfg
    return repos
def checkout_repo(conf):
    log.info(conf)
    d = conf['path']
    if not os.path.exists(d):
        parent = os.path.dirname(os.path.abspath(d))
        mkdirs(parent)
        with cd(parent):
            system('git clone {}'.format(conf['url']))
    sha1 = conf['sha1now']
    with cd(d):
        system('git checkout -q {}'.format(sha1))
def checkout(args):
    init(args)
    with cd(args.directory):
        # Directories are relative to the location of ini files, for now.
        repos = read_modules()
        for repo, cfg in repos.iteritems():
            checkout_repo(cfg)
def prepare(args):
    """
    This has p4 interactions.
    Run 'p4 edit' on each file that needs to be changed.
    """
    init(args)
    with cd(args.directory):
        repos = read_modules()
        for name, cfg in repos.iteritems():
            path = cfg['path']
            with cd(path):
                sha1 = capture('git rev-parse HEAD').strip()
                log.info('{} {} {}'.format(sha1, name, path))
            log.info(os.getcwd())
            log.info(name)
            assert os.path.exists(name + '.ini')
            prepared = name + '.ini.bak'
            with open(prepared, 'w') as fp:
                write_repo_config(fp, cfg)

def map_sha1s(listing):
    """
    Example:
    5d527739295c82bf4a141532d61019b9d155cc99 DALIGNER (heads/master)
    3e2231218d94f1f2a9083ae5695fb0d888b3e405 FALCON (0.2JASM-261-g3e22312)
    64d08e363e88b9356b587f2524fdc299a61d0791 pith (remotes/origin/HEAD)
    ...

    => {'DALIGNER': '5d527739295c82bf4a141532d61019b9d155cc99', ...}
    """
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
def gitmodules_as_config(content):
    """Turn the .gitmodules file (content)
    into a valid ConfigParser file.
    """
    re_initial_ws = re.compile('^\s*(.*)$', re.MULTILINE)
    config = re_initial_ws.sub(r'\1', content)
    log.info(config)
    return config
def convert(args):
    """Using .git and .gitmodules from args.directory,
    write *.ini for each submodule, after moving
    original directory to .bak and re-creating.

    This is used only to convert our old submodules to this system.
    Note that 'pb-sync' should be run first.
    """
    init(args)
    group = dict()
    repos = dict()
    group['repos'] = repos
    # For now, require full path to '.gitmodules'.
    directory = os.path.abspath(args.directory)
    gitmodules = os.path.join(directory, '.gitmodules')
    log.info('Converting from "{}"...'.format(gitmodules))
    fp = StringIO.StringIO(gitmodules_as_config(open(gitmodules).read()))
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
    rename(directory, directory + '.bak')
    mkdirs(directory)
    for name, cfg in repos.iteritems():
        fn = os.path.join(directory, '{}.ini'.format(name))
        log.info('Writing {}'.format(fn))
        with open(fn, 'w') as fp:
            write_repo_config(fp, cfg)
def main(argv):
    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--directory',
            default='.',
            help='Directory of submodules')
    parser.add_argument('-v', '--verbose',
            action='store_true')
    subparsers = parser.add_subparsers()

    p = subparsers.add_parser('checkout',
            #aliases=['co'],
            )
    p.set_defaults(func=checkout)

    p = subparsers.add_parser('convert',
            help='Convert .gitmodules to this system.',
            )
    p.set_defaults(func=convert)

    p = subparsers.add_parser('prepare',
            help='Prepare to submit the current changes, staged as *.ini.bak files.',
            )
    p.set_defaults(func=prepare)

    p = subparsers.add_parser('submit',
            help='Submit the prepared changes (*.ini.bak).',
            )
    p.add_argument('-c', '--change',
            default='default',
            help='Perforce changenum. Use this to avoid submitting your currently opened files.',
            )
    p.add_argument('-b', '--bug',
            default='999999',
            help='Bugzilla number.',
            )
    #p.set_defaults(func=submit)
    args = parser.parse_args(argv[1:])
    args.func(args)

main(sys.argv)
