"""
This is for one-off use of pb-git-convert-from-submodules. After it has
served its purpose, we can delete this file.
"""
# Chris, Can this still be
# useful for pulling new submodule sets into p4?
# Implement 'pb-git add' first, then see.
from . import cmds
import ConfigParser as configparser
import os
import pprint
import re
import StringIO


log = cmds.log

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
    with cmds.cd(d):
        listing, errs = cmds.capture('git submodule status')
        if errs: log.debug(errs)
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
    Note that 'pb-sync' should be cmds first.
    """
    cmds.init(args)
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
        repos[name]['sha1'] = sha1
    log.info(pprint.pformat(repos))
    for name, cfg in repos.iteritems():
        fn = os.path.join(directory, '{}.ini'.format(name))
        log.info('Writing {}'.format(fn))
        with open(fn, 'w') as fp:
            cmds.write_repo_config(fp, cfg)
    with cmds.cd(directory):
        try:
            cmds.system('p4 add *.ini')
        except IOError:
            log.exception('"convert" was already run on this directory. Try `pb-git -d $DIR prepare`, followed by `pb-git -d $DIR submit`.')

def migrate(args):
    """Move old git-submodules parent repo,
    'p4 sync -f dir',
    and re-checkout.
    """
    cmds.init(args)
    # We used to move and re-create, but that is not really needed immediately.
    # The submodules can exist until a new one is added. Even then,
    # things will work until someone actually performs a
    # git-submodule command locally.
    cmds.rename(directory, directory + '.bak')
    log.warning('Your old work is now in "{}".'.format(directory + '.bak'))
    cmds.system('p4 sync -f {}/...'.format(directory))
    cmds.checkout(args)
    log.warning('To reiterate, your old work is now in "{}".'.format(directory + '.bak'))
