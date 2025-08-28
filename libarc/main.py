import argparse # to parse command line arguments
import configparser # used to read configuration files similar to Microsoft INI format

from datetime import datetime
import grp, pwd     # read users/groupp database on Unix
from fnmatch import fnmatch # to aid support for filename pattern matching like .gitignore
import hashlib # in order to use SHA-1 function (cryptographic hashing)
from math import ceil
import os       # os and os.path gives filesystems abstraction
import re # support for regular expressions
import sys # access actual command line arguments in sys.argv
import zlib # to help with compression

argparser = argparse.ArgumentParser(description="Lightweight reimplemented git CLI")

# Declare that CLI will use subcommands (subparsers in argparser slang) such as init, add 
# and that it is required for every invocation of the commmand e.g git COMMAND
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
        # force is set to True while creating a new repo and the checks here are hence not necessary
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


# implementation difference between repo_dir and repo_file is that for repo_dir, it creates the entire directory path you pass to it. It is for creating
# directory structures, while repo_file only creates the containing directories for the file you are about to create. It is for preparing a path to write a file to.

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


    # if repo_dir returns None or empty string (indicating failure) an AssertionError is raised
    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # repo_file in these provides file path as argument for the open function, the write option creates the file not the repo_file

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
    

## Writing Objects
# More like reverse of reading the object, we insert header, compute the hash, zlib-compress everything and write the result in the correct
# location. 

def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # Compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        # ensures we only write objects that do not previously exists since Git objects are immutable and are only stored once
        if not os.path.exists(path): 
            with open(path, 'wb') as f:
                # Compress and write
                f.write(zlib.compress(result))
    return sha


## Working With Blobs
'''
Blobs are one of the types of Git object, and are the simplest of those four types, because they have no actual format. Blobs are user's data:
the content of every file you put in git (main.c, logo.png, README.md) is stored as blob. MAkes them easy to manipulate since they have no actual syntax
or constraints beyond basic object storage mechanism: they are just unspecified data
Creating a GitBlob is trivial, the serialize() and deserialize() functions just have to store and return their input unmodified. 
'''

class GitBlob(GitObject):
    fmt = b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data



## cat-file command
'''
Prints the raw contents of an object to stdout, uncompressed and without the git header. Our version will take in two arguments,
a type and an object identifier
SYNTAX: arc cat-file TYPE OBJECT
'''
argsp = argsubparsers.add_parser("cat-file", help="Provide content of repository objects")

argsp.add_argument("type", metavar="type", choices=["blob", "commit", "tag", "tree"])
argsp.add_argument("object", metavar="object", help="The object to display")

# we then implement the functions which just call into existing code we wrote earlier
def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize()) 


# object find implementation, still to be changed I think, for now just return one of its arguments unmodified like this
def object_find(repo, name, fmt=None, follow=True):
    return name

'''
The reason for just implementing the object_find() like this for now, is because Git has a lot of ways to refer to object, such as
full hash, short hash, tags, etc. object_find() would be our name resolution function. It will be implemented later, so for now it is just a temporary placeholder
so for now, the only way we can refer to an object is by its full hash
'''


'''
hash-object command is basically the opposite of cat-file, it reads a file, computes its hash as an object, either storing it in the repo
(if the -w flag passed) or just printing its hash.
Syntax here: arc hash-object [-w] [-t TYPE] FILE
'''

argsp = argsubparsers.add_parser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from the file"
)

argsp.add_argument("-t",
                   metavar="type", dest="type", choices=["blob", "commit", "tag", "three"],
                   default="blob", help="Specify the type")
argsp.add_argument("-w", dest="write", action="store_true", 
                   action="store-true",
                   help="Actually wriite the object into the database")
argsp.add_argument("path", help="Read object from <file> ")

# We then ceate a bridge function for it, and the actual implementaion is very simple
def cmd_hash_object(args):
    if args.write:
        repo = repo_find() 
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)   
        print(sha)                                                                                                                                                                                                                                                                                                                                                                                               
 