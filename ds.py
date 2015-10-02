#!/usr/bin/env python2.7
from contextlib import contextmanager
import argparse
import ConfigParser as configparser
import logging
import os
import pprint
import StringIO
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
def init(args):
    logging.getLogger().setLevel(logging.DEBUG)
    if args.verbose:
        logging.getLogger().setLevel(logging.NOTSET)
    group = open(args.group_file).read()
    group = eval(group) # N.B. code injection
    log.info(args.func)
    log.info(args)
    log.info(repr(group))
    if args.reformat_group_file:
        with open(args.group_file, 'w') as ifs:
            ifs.write(pprint.pformat(group) + '\n')
    return group
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
def checkout_repo(conf):
    log.info(conf)
    d = conf['dir']
    if not os.path.exists(d):
        with cd(os.path.dirname(os.path.abspath(d))):
            system('git clone {}'.format(conf['remote']))
    ini = get_ini(conf)
    log.info(ini)
    sha1 = get_sha1(ini)
    with cd(d):
        system('git checkout {}'.format(sha1))
def checkout(args):
    group = init(args)
    with cd(os.path.dirname(os.path.abspath(args.group_file))):
        # Directories are relative to the location of group_file, for now.
        for repo, repo_conf in group['repos'].iteritems():
            checkout_repo(repo_conf)
def main(argv):
    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-g', '--group-file',
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
    args = parser.parse_args(argv[1:])
    args.func(args)

main(sys.argv)
