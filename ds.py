#!/usr/bin/env python2.7
import argparse
import sys

def run(args):
    pass
def main(argv):
    parser = argparse.ArgumentParser()
    #parser.add_argument()
    args = parser.parse_args(argv[1:])
    print args
    run(args)

main(sys.argv)
