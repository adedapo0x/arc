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
class GitRepository:
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        # False is set to True while creating a new repo and the checks here are hence not necessary
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
    return os.path.join(repo.gitdir, *path)


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
    

# Function to create new repository
def repo_create(path):
    '''Create new repository at path'''
    repo = GitRepository(path, True)
    
    # Making sure path either doesn't exists or is an empty dir
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory")
        # check if gitdir exists and if it is empty
        if not os.path.exists(repo.gitdir) and os.listdir(repo.gitdir): 
            raise Exception(f"{path} is not empty")
        
    else:
        os.makedirs(repo.worktree)


    # if repo_dir returns None or empty string (indicating failure) and AssertionError is raised
    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)


    #.git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository, edit this file 'description' to name the repository.\n")

    #.git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo


# Configuration file setup
def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret


# Implement the "init" command

argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository")
argsp.add_argument("path", metavar="directory",nargs="?", default=".", help="Where to create the repository")

def cmd_init(args):
    repo_create(args.path)


# Implementing repo_find() function that finds the root of the current directory that we are currently working in
# We identify a path as a repository by the presence of a .git directory

def repo_find(path=".", required=True):
    path = os.path.realpath(path)  # gets absolute path

    # check if path contains a .git directory, if found, we are in root
    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path) # return GitRepository object
    
    # if we haven't returned, move to parent directory to check
    parent = os.path.realpath(os.path.join(path, ".."))
    # check if we have reached the root directory
    if parent == path:
        if required: 
            raise Exception("No Git directory")
        else:
            return None
        
    return repo_find(parent, required)

 
# Git Objects, most things in Git are stored as objects
'''
An object starts with an header that specifies its type. There are 4 main types of objects
 - blob: stores file content
 - commit: Records snapshot of the project
 - tag: Marks specific points in history
 - tree: Represents directories and files
The header is followed by an ASCII space (0x20) ie a regular space character
then the size of the object in bytes, 
then the null byte (0x00)
then actual content of the object
Note that all objects are stored compressed with zlib
'''

# We now create a generic object for all git object types
# We create the object with two unimplemented methods that must be implemented by subclasses, 
# the serialize() and deserialize() method with an __init__ constructor that creates a new empty object using init method or uses data if provided to create an object

class GitObject:
    def __init__(self, data=None):
        if data != None:
            self.deserialize(data)
        else:
            self.init()

    def serialize(self, repo):
        '''
        This function MUST BE IMPLEMENTED by subclasses.
        It must read the object's content from self.data, a byte string and convert it to a meaningful representation which depends on each subclass
        '''
        raise Exception("Unimplemented!")
    def deserialize(self, data):
        raise Exception("Unimplemented!")
    
    def init(self):
        pass # Do nothing, this is a reasonable default

# Reading Objects

'''
To read an object we get its SHA 1 hash, then compute path from it's hash. Since first two character are directory, the rest represents the file
So we would have first two characters then a directory delimiter (/) then look up the remaining part in the "objects" directory in gitdir.
We then read the file as a binary file and decompress it using zlib
After decompression, extract the two header components: the object type and its size, from the type we determine which class to use .
Convert size to Python integer and check if it matches. Then call the correct constructor for that object format 
'''

def object_read(repo, sha):
    '''
    Read the object SHA from Git repository repo. Return a Git object whose exact type depends on the object
    '''

    path = repo_file(repo, "objects", sha[0:2], sha[2:])
    if not os.path.isfile(path):
        return None
    
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        ## Read object type
        x = raw.find(b' ') # finds the position of the first space character in raw data
        fmt = raw[0:x] # extracts everything from beginning of raw up until just before the space character. This is the object type
                        # since the format is that the header that specifies the type then space then size then null byte then actual content

        ## Read and validate the object size
        y = raw.find(b'\x00', x) # finds the position of the null character starting from x
        
        # this gets the size, as it extracts the bytes between the space and the null byte which would contain the size, then converts it to an ASCII string
        # then to an integer which is stored in variable size
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1: # Since y + 1 is where the content begins so we check if the size matches the actual content length
            raise Exception(f"Malformed object {sha}: bad length")
        
        # Pick constructor
        match fmt:
            case b'commit': c=GitCommit
            case b'tree'  : c=GitTree
            case b'tag'   : c=GitTag
            case b'blob'  : c=GitBlob
            case _:
                raise Exception(f"Unknown type {fmt.decode("ascii")} for object {sha}")   
            
        # Call constructor and return object
        return c(raw[y+1:])




    



