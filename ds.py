#!/usr/bin/env python2.7
import argparse
import logging
import pprint
import sys

logging.basicConfig()
log = logging.getLogger(__name__)

def sync_repo(conf):
    log.info(conf)
def run(args):
    logging.getLogger().setLevel(logging.INFO)
    if args.verbose:
        logging.getLogger().setLevel(logging.NOTSET)
    group = open(args.group_file).read()
    group = eval(group) # N.B. code injection
    log.info(args)
    log.info(repr(group))
    if args.reformat_group_file:
        with open(args.group_file, 'w') as ifs:
            ifs.write(pprint.pformat(group) + '\n')
    for repo, repo_conf in group['repos'].iteritems():
        sync_repo(repo_conf)
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
    args = parser.parse_args(argv[1:])
    run(args)

main(sys.argv)
