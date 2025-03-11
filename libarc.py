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
import zlib # to compress



