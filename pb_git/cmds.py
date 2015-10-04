"""
We expect to see a foo.ini file for every repo 'foo'.

We use a separate file for each module b/c that makes them easier to
update in p4.
"""
from contextlib import contextmanager
import ConfigParser as configparser
import glob
import logging
import os
import shlex
import StringIO
import subprocess
import sys

log = logging.getLogger(__name__)
cd_depth = 0

@contextmanager
def cd(newdir):
    global cd_depth
    prevdir = os.getcwd()
    log.debug("[{}]cd '{}' from '{}'".format(cd_depth, newdir, prevdir))
    os.chdir(os.path.expanduser(newdir))
    cd_depth += 1
    try:
        yield
    finally:
        cd_depth -= 1
        log.debug("[{}]cd '{}' from '{}'".format(cd_depth, newdir, prevdir))
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
    logging.basicConfig()
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
    for key, val in sorted(cfg.iteritems()):
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
            system('git clone {} {}'.format(conf['url'], conf['path']))
    sha1 = conf['sha1']
    with cd(d):
        try:
            system('git checkout -q {}'.format(sha1))
        except Exception:
            system('git fetch origin')
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
                if sha1new == cfg['sha1']:
                    continue
                sha1old = cfg['sha1']
                cfg['sha1'] = sha1new
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
    if args.dry_run:
        system_perm = log.info
    else:
        system_perm = system
    with cd(args.directory):
        n = 0
        for fnnew in glob.glob('*.ini.bak'):
            fnold = fnnew[:-4]
            if not system('diff -qw {} {}'.format(fnnew, fnold), checked=False):
                continue
            with open(fnold) as fp:
                cfgold = read_repo_config(fp)
            with open(fnnew) as fp:
                cfgnew = read_repo_config(fp)
            sha1old = cfgold['sha1']
            sha1new = cfgnew['sha1']
            gh_user = 'PacificBiosciences' #TODO: Sometimes this is wrong.
            gh_repo = fnold[:-4] # Probably?
            compare_link = 'https://github.com/{}/{}/compare/{}...{}'.format(
                gh_user, gh_repo, sha1old, sha1new)
            mout.write('{}\n'.format(compare_link))
            system_perm('p4 edit {}'.format(fnold))
            system_perm('cp -f {} {}'.format(fnnew, fnold))
            n += 1
        system_perm('p4 revert -a ...')
        msg = mout.getvalue()
        system_perm('p4 submit -c {} -d "{}"'.format(
            args.change, msg))
        if n == 0:
            return
