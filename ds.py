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
def system(call, checked=True):
    log.info(call)
    rc = os.system(call)
    if rc and checked:
        raise Exception('{rc} <- {call!r}'.format(rc=rc, call=call))
    return rc
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
    Create *.ini.bak.
    TODO: Only create if different.
    """
    init(args)
    with cd(args.directory):
        repos = read_modules()
        for name, cfg in repos.iteritems():
            path = cfg['path']
            with cd(path):
                sha1new = capture('git rev-parse HEAD').strip()
                log.debug('{} {} {}'.format(sha1new, name, path))
                if sha1new == cfg['sha1now']:
                    continue
                sha1old = cfg['sha1now']
                cfg['sha1now'] = sha1new
            log.info(os.getcwd())
            log.info(name)
            assert os.path.exists(name + '.ini')
            prepared = name + '.ini.bak'
            with open(prepared, 'w') as fp:
                write_repo_config(fp, cfg)
def submit(args):
    """
    This has p4 interactions.
      'p4 edit' on each file that needs to be changed.
      'p4 revert -a'
      'p4 submit'
    TODO: Finally remove old *.ini.bak?
    """
    init(args)
    mout = StringIO.StringIO()
    mout.write('{}\n'.format(args.message))
    mout.write('bug #{}\n'.format(args.bug))
    mout.write('\n')
    fsystem = log.info
    with cd(args.directory):
        n = 0
        for fnnew in glob.glob('*.ini.bak'):
            fnold = fnnew[:-4]
            if not system('diff -qw {} {}'.format(fnnew, fnold), checked=False):
                log.info("SAME!")
                continue
            with open(fnold) as fp:
                cfgold = read_repo_config(fp)
            with open(fnnew) as fp:
                cfgnew = read_repo_config(fp)
            sha1old = cfgold['sha1now']
            sha1new = cfgnew['sha1now']
            gh_user = 'PacificBiosciences' #TODO: Sometimes this is wrong.
            gh_repo = fnold[:-4] # Probably?
            compare_link = 'https://github.com/{}/{}/compare/{}...{}'.format(
                gh_user, gh_repo, sha1old, sha1new)
            mout.write('{}\n'.format(compare_link))
            fsystem('p4 edit {}'.format(fnold))
            fsystem('cp -f {} {}'.format(fnnew, fnold))
            n += 1
        fsystem('p4 revert -a ...')
        msg = mout.getvalue()
        fsystem('p4 submit -c {} -d "{}"'.format(
            args.change, msg))
        if n == 0:
            return
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
    p.add_argument('-m', '--message',
            default='Updating SHA1s.',
            help='Brief message at top of submit description. Bug # and github links will be added.',
            )
    p.set_defaults(func=submit)
    args = parser.parse_args(argv[1:])
    args.func(args)

main(sys.argv)
