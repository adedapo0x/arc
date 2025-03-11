import argparse # to parse command line arguments
import configparser # used to read configuration files similar to Microsoft INI format

from datetime import datetime
import grp, pwd
from fnmatch import fnmatch # to aid support for filename pattern matching like .gitignore
import hashlib # in order to use SHA-1 function (cryptographic hashing)
from math import ceil
import os
import re # support for regular expressions
import sys # access actual command line arguments 
import zlib # to help with compression


argparser = argparse.ArgumentParser(description="Lightweight reimplemented git CLI")

# Declare that CLI will use subcommands (subparsers in argparser slang) such as init, add 
# and that it is required for every invocation of the commmand
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True 


def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "add"          : cmd_add(args)
        case "cat-file"     : cmd_cat_file(args)
        case "check-ignore" : cmd_check_ignore(args)
        case "checkout"     : cmd_checkout(args)
        case "commit"       : cmd_commit(args)
        case "hash-object"  : cmd_hash_object(args)
        case "init"         : cmd_init(args)
        case "log"          : cmd_log(args)
        case "ls-files"     : cmd_ls_files(args)
        case "ls-tree"     : cmd_ls_tree(args)
        case "rev-parse"    : cmd_rev_parse(args)
        case "rm"           : cmd_rm(args)
        case "show-ref"     : cmd_show_ref(args)
        case "status"       : cmd_status(args)
        case "tag"          : cmd_tag(args)
        case _              : print("Bad command. ")




