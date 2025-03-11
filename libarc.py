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
        case "ls-tree"      : cmd_ls_tree(args)
        case "rev-parse"    : cmd_rev_parse(args)
        case "rm"           : cmd_rm(args)
        case "show-ref"     : cmd_show_ref(args)
        case "status"       : cmd_status(args)
        case "tag"          : cmd_tag(args)
        case _              : print("Bad command. ")


# An object to model the git repository
class GitRepository(object):
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")
        
        # Read configuration file from .git/config
        self.conf = configparser.ConfigParser() # initialize configuration parser
        cf = repo_file(self, "config") # determine the config file path

        if cf and os.path.exists(cf): # check if configuration file exists
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")
        
        # Checking that the format version is 0, else it is incompatible
        if not force: # Only runs when force is False (ie checks are not being skipped)
            version = int(self.conf.get("core", "repositoryformatversion"))
            if version != 0:
                raise Exception(f"Unsupported repository format version: {version}")


# Utility functions to compute file paths and create missing directory structure

# general path building function
def repo_path(repo, *path):
    # Compute path under repo gitdir
    return os.path.join(repo.getdir, *path)


def repo_dir(repo, *path, mkdir=False):
    '''Same as repo_path but mkdir *path if absent if mkdir i.e makes a directory out of the path if mkdir=True and it was previously not a directory'''
    path = repo_path(repo, *path)
    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception(f"Not a directory {path}")
        
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None


def repo_file(repo, *path, mkdir=False):
    '''Difference between repo_file and repo_dir is file version only creates directory for the last component'''
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)
    





