"""
We expect to see a foo.ini file for every repo 'foo'.

We use a separate file for each module b/c that makes them easier to
update in p4.
"""
from contextlib import contextmanager
import ConfigParser as configparser
import functools
import glob
import logging
import os
import shlex
import shutil
import StringIO
import subprocess
import sys
import tempfile

log = logging.getLogger(__name__)
info_mod = logging.INFO+2
info_sys = logging.INFO+1
info_basic = logging.INFO+0
log_info_sys = functools.partial(log.log, info_sys)
log_info_mod = functools.partial(log.log, info_mod)
cd_depth = 0

@contextmanager
def cd(newdir, cleanup=lambda: True):
    global cd_depth
    prevdir = os.getcwd()
    log.info("[{}]cd '{}' from '{}'".format(cd_depth, newdir, prevdir))
    os.chdir(os.path.expanduser(newdir))
    cd_depth += 1
    try:
        yield
    finally:
        cd_depth -= 1
        log.info("[{}]cd '{}' back from '{}'".format(cd_depth, prevdir, newdir))
        os.chdir(prevdir)
        cleanup()

def system(call, checked=True):
    """Raise IOError on failure if checked.
    """
    log.log(info_sys, call)
    rc = os.system(call)
    if rc and checked:
        raise IOError('{rc} <- {call!r}'.format(rc=rc, call=call))
    return rc

def capture(call, log=log_info_sys):
    """Return stdout, stderr.
    Raise IOError on failure.
    """
    log('`{}`'.format(call))
    # return subprocess.check_output(shlex.split(call))
    # Ugh! p4 commands often write to stderr when there is no error,
    # so we should trap that too. Why does anybody like p4?
    badvars = set(["P4DIFF", "P4MERGE"])
    env = dict((k, v) for k, v in os.environ.iteritems() if k not in badvars)
    proc = subprocess.Popen(shlex.split(call),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
            )
    out, err = proc.communicate()
    if out: log('{}'.format(out.rstrip()))
    if proc.returncode:
        #log.debug(out)
        raise IOError(err)
    return out, err

def rename(old, new):
    log.log(info_sys, 'Moving "{}" to "{}"'.format(old, new))
    os.rename(old, new)

def init_argparse(parser):
    """Add our basic arguments for an ArgumentParser.
    """
    parser.add_argument('-d', '--directory',
            default='.',
            help='Directory of submodules')
    parser.add_argument('-v', '--verbosity',
            default=1, type=int,
            help='0=>only errors/warnings; 1=>modifications; 2=>syscalls; 3=>info; 4=>debug')

def init(args):
    fmt = '[%(levelname)s] %(message)s'
    fmt_debug = '[%(levelname)s](%(pathname)s:%(lineno)s)\n\t%(message)s'
    levels = {
            0: (logging.WARNING, fmt),
            1: (info_mod, fmt),
            2: (info_sys, fmt),
            3: (info_basic, fmt),
            4: (logging.NOTSET, fmt_debug),
    }
    lvl, fmt = levels[args.verbosity]
    logging.addLevelName(info_mod, 'SYS')
    logging.addLevelName(info_sys, 'SYS')
    logging.addLevelName(info_basic, 'INFO')
    fmtr = logging.Formatter(fmt=fmt)
    hdlr = logging.StreamHandler(sys.stderr)
    hdlr.setFormatter(fmtr)
    root = logging.getLogger()
    root.addHandler(hdlr)
    root.setLevel(lvl)

def mkdirs(d):
    if not os.path.isdir(d):
        log.log(info_sys, 'mkdir -p {}'.format(d))
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
        log.log(info_basic, 'Found "{}"'.format(fn))
        cfg = read_repo_config(open(fn))
        log.debug("{!r} -> {!r}".format(fn, cfg))
        name = fn[:-4]
        repos[name] = cfg
    return repos

def checkout_repo(conf):
    d = conf['path']
    log.debug('checkout_repo at {!r}'.format(d))
    modified = False
    if not os.path.exists(d):
        parent = os.path.dirname(os.path.abspath(d))
        mkdirs(parent)
        with cd(parent):
            system('git clone {} {}'.format(conf['url'], conf['path']))
            modified = True
    sha1 = conf['sha1']
    checkout_cmd = 'git -C {} checkout {}'.format(d, sha1)
    try:
        out, err = capture(checkout_cmd)
    except Exception as e:
        log.debug('SHA1 not found. Fetching.', exc_info=True)
        capture('git -C {} fetch origin'.format(d))
        modified = True
        out, err = capture(checkout_cmd)
    if 'Previous' in err or modified:
        log.log(info_mod, '{}\n{}'.format(
            checkout_cmd, err.strip()))
    else:
        log.debug(err.strip())
    if out:
        # This seems to be always empty, but I am not positive.
        log.debug(out.strip())

def checkout(args):
    init(args)
    with cd(args.directory):
        # Directories are relative to the location of ini files, for now.
        repos = read_modules()
        for repo, cfg in repos.iteritems():
            checkout_repo(cfg)
@contextmanager
def tempdir():
    dirpath = tempfile.mkdtemp()
    def cleanup():
        shutil.rmtree(dirpath)
    with cd(dirpath, cleanup):
        yield dirpath

def verify_repo(name, cfg, sha1):
    """
    Here is one way:
        curl -s -o /dev/null -w "%{http_code}" https://github.com/pb-cdunn/FALCON-integrate/commit/ab367c696
    But we would need to translate the URL to https, which can be difficult for private modules
    using API keys.
    
    Instead, we will simply perform a checkout.
    We plan to have a cache, so we can let this be slow for now.
    """
    # We expect this to occur in a temp-dir.
    mkdirs(name)
    with cd(name):
        path = cfg['path']
        log_info_mod('Verifying {} {} {}'.format(name, sha1, path))
        checkout_repo(cfg)

def verify(args):
    """
    Check with GitHub to see whether These commits are available.
    """
    init(args)
    with cd(args.directory):
        repos = read_modules()
        sha1s = dict()
        for name, cfg in repos.iteritems():
            path = cfg['path']
            sha1new, errs = capture('git -C {} rev-parse HEAD'.format(path))
            if errs:
                log.debug(errs)
            sha1new = sha1new.strip()
            log.debug('Expecting {} @ {}'.format(path, sha1new))
            sha1s[name] = sha1new
        with tempdir():
            for name, cfg in repos.iteritems():
                verify_repo(name, cfg, sha1s[name])

def prepare(args):
    """
    for each mod:
        Create mod.ini.bak
        diff mod.ini.bak mod.ini
        if different:
            p4 edit mod
            mv mod.ini.bak mod.ini
    """
    init(args)
    with cd(args.directory):
        p4_opened, _ = capture('p4 opened -m 1')
        if _: log.debug(_.strip())
        p4_opened = p4_opened.strip()
        #if 'not opened on this client' not in _:
        if p4_opened:
            log.warning('Already opened in p4:\n' + repr(p4_opened))
            # We need these produce proper http links, in case this is run twice.
            out, err = capture('p4 revert *.ini')
            if out:
                log.debug(repr(out.strip()))
            if err:
                log.debug(repr(err.strip()))
            #capture('p4 sync -f *.ini') # Probably not needed.

        repos = read_modules()
        changes = list()
        for name, cfg in repos.iteritems():
            path = cfg['path']
            sha1new, errs = capture('git -C {} rev-parse HEAD'.format(path))
            if errs:
                log.debug(errs)
            sha1new = sha1new.strip()
            log.debug('Preparing {} {} {}'.format(sha1new, name, path))
            if sha1new == cfg['sha1']:
                continue
            sha1old = cfg['sha1']
            cfg['sha1'] = sha1new
            assert os.path.exists(name + '.ini')
            prepared = name + '.ini.bak'
            fnold = name + '.ini'
            with open(prepared, 'w') as fp:
                log_info_mod('Writing to {!r}'.format(prepared))
                write_repo_config(fp, cfg)
            capture('p4 edit {}'.format(fnold), log=log_info_mod)
            changes.append((name, cfg, sha1new))
        if not args.no_verify:
            # Verify that changes are available in GitHub.
            with tempdir():
                for name, cfg, sha1 in changes:
                    verify_repo(name, cfg, sha1)
        mout = StringIO.StringIO()
        n = prepare_for_submit(mout, dry_run=False)
        capture('p4 diff ...')
        msg = mout.getvalue()
        sys.stdout.write('Please add these links to your submit message:\n' + msg)

def prepare_for_submit(mout, dry_run=False):
    """Assume this is running in parent dir of git-modules.
    """
    if dry_run:
        system_perm = log_info_mod
    else:
        system_perm = functools.partial(capture, log=log_info_mod)
    n = 0
    for fnnew in glob.glob('*.ini.bak'):
        fnold = fnnew[:-4]
        try:
            capture('diff -qw {} {}'.format(fnnew, fnold))
            system_perm('rm -f {}'.format(fnnew))
            continue
        except IOError:
            pass # They differ.
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
        system_perm('mv -f {} {}'.format(fnnew, fnold))
        n += 1
    system_perm('p4 revert -a ...')
    return n

def submit(args):
    """
    DEPRECATED. It is better to run 'p4 submit' yourself.

    This has p4 interactions.
      'p4 revert -a'
      'p4 submit'
    The user must run 'p4 edit' manually on the chosen '*.ini' files.
    """
    init(args)
    with cd(args.directory):
        mout = StringIO.StringIO()
        mout.write('{}\n'.format(args.message))
        mout.write('bug #{}\n'.format(args.bug))
        mout.write('\n')
        n = prepare_for_submit(mout, args.dry_run)
        if n == 0:
            #raise Exception('Nothing to do. Check `p4 opened`.')
            return
        msg = mout.getvalue()
        system_perm('p4 submit -d "{}"'.format(
            msg))
        system_perm(r'\rm -f *.ini.bak')
