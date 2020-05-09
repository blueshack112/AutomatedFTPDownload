import sys
import os
from ftplib import FTP
import getopt
import platform
import re
import yaml
import inspect
import time
import traceback
from os.path import expanduser
from datetime import datetime
import zipfile
from zipfile import ZipFile
import tarfile
from tarfile import TarFile


downloadedFiles = ['Doc/t/test.tar','Doc/t/Hassan.zip']

for i in downloadedFiles:
    file = i

    # Check if file is zip file and unzip it
    if zipfile.is_zipfile(file):
        with zipfile.ZipFile(file, 'r') as zip_ref:
            zip_ref.extractall('Doc/t/')

        print ("Unzipped {}".format(file))
    # Check if tar file
    elif tarfile.is_tarfile(file):
        tarFile = tarfile.open(file)
        tarFile.extractall('Doc/t/') # specify which folder to extract to
        tarFile.close()
        print ("Untarred {}".format(file))