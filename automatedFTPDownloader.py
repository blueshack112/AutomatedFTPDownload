#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
AutomatedFTPDownloader

@contributor: Hassan Ahmed
@contact: ahmed.hassan.112.ha@gmail.com
@owner: Patrick Mahoney
@version: 1.0.4

Downloads files from IMC using a YAML file for credentials and default settings
"""

# Help message
HELP_MESSAGE = """
TODO: Document this part
Usage:
    The script is capable of running without any argument provided. All behavorial
    variables will be reset to default.
    
    $ python3 automatedFTPDownloader.py [options]
    
Parameters/Options:
    -h  | --help            : View usage help and examples
    -f  | --file            : Path to the configuration file containing FTP hostnames, users, passwords, and paths
        |                       - First default in current working directory, will search for "ftp.yaml"
        |                       - Default in %APPDATA%/local/ftp.yaml on Windows
        |                       - Default in $HOME/ftp.yaml on Linux
    -o  | --output          : Path for the output files to be downloaded at (directory path)
        |                       - Default in %USERPROFILE%/Downloads on Windows
        |                       - Default in $HOME on Linux
    -p  | --preserve        : (Force-disabled right now) Do not delete older files that start with 'SureDone_' in the download directory
        |                       - This funciton is limited to default download locations only.
        |                       - Defining custom output path will render this feature useless.
    -s  | --site            : A specific site in the YAML file that should be targetted to connect and download files from
    -u  | --unzip           : If provided, all the .zip and .tar files downloaded from FTP sites will be unzipped in the root folder as well
    -v  | --verbose         : Show outputs in terminal as well as the log file

Example:
    $ python3 automatedFTPDownloader.py

    $ python3 automatedFTPDownloader.py -f [config.yaml]
    $ python3 automatedFTPDownloader.py -file [config.yaml]

    $ python3 automatedFTPDownloader.py -f [config.yaml] -o [Downloads/]
    $ python3 automatedFTPDownloader.py -file [config.yaml] --output [Downloads/]

    $ python3 automatedFTPDownloader.py -f [config.yaml] -o [XYZFiles/today/] -s XYZ_ftp -v -p
    $ python3 automatedFTPDownloader.py -file [config.yaml] --output [XYZFiles/today/] --site XYZ_ftp --verbose --preserve
"""

# Imports
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

currentMilliTime = lambda: int(round(time.time() * 1000))

START_TIME = datetime.now()
RUN_TIME = currentMilliTime()
# Connects to remote ftp server using credentials from get_credentials() using a YAML file
def main(argv):
    localFrame = inspect.currentframe()
    # Parse arguments
    ftpYAMLPath, outputDIRPath, preserveOldFiles, verbose, unzipFiles, ftpConfigs, targetFTPSite = parseArgs(argv)
    # Force-enablinbg the preserve feature in order to disable purging
    preserveOldFiles = True

    LOGGER.writeLog("FTP YAML path: {}".format(ftpYAMLPath), localFrame.f_lineno, severity='normal')
    LOGGER.writeLog("Local directory: {}".format(outputDIRPath), localFrame.f_lineno, severity='normal')
    LOGGER.writeLog("Preserve: {}".format(preserveOldFiles), localFrame.f_lineno, severity='normal')
    LOGGER.writeLog("Verbose: {}".format(verbose), localFrame.f_lineno, severity='normal')
    LOGGER.writeLog("Unzip files: {}".format(unzipFiles), localFrame.f_lineno, severity='normal')

    # Iterate over all the ftp sites if target ftp site is ".*_.*"
    if targetFTPSite == '.*_.*':
        targetFTPSite = []
        for key in ftpConfigs.keys():
            targetFTPSite.append(key)
    else:
        targetFTPSite = [targetFTPSite]
    LOGGER.writeLog("Target sites: {}".format(targetFTPSite), localFrame.f_lineno, severity='normal')
    
    allFilesDownloaded = []
    
    # Spin through the list of target sites
    for site in targetFTPSite:
        # Connect to FTP and download all files in the specified directory
        downloadedFiles = connectToFTP(ftpConfigs[site], site, outputDIRPath)

        # Unzip downloaded files if present
        if unzipFiles:
            unzipZippedFiles(outputDIRPath, downloadedFiles)
        
        allFilesDownloaded = allFilesDownloaded + downloadedFiles
    
    safeExit(outputDIRPath, allFilesDownloaded, marker='execution-complete')

def safeExit(downloadPath, downloadedFiles, marker=''):
    """
    Function that will perform a basic print job at the end of the script.

    Parameters
    ----------
        - downloadPath : str
            Path to the download directory
        - marker : str
            An identifier of what initiated the function.
            Currently we only have one initiator of this function, could be more later.
    """
    # Get ending time
    END_TIME = datetime.now()

    # Get runtime length
    executionTime = currentMilliTime() - RUN_TIME
    downloadedFilesizes = []
    for f in downloadedFiles:
        file = os.path.join(downloadPath, f)
        size = os.path.getsize(file)
        downloadedFilesizes.append(
            {
                'name': file,
                'size': size,
            }
        )

    # For execution-completed
    if marker == 'execution-complete':
        print ("=================================================================")
        print ("SCRIPT EXECUTED SUCCESSFULLY")
        print ("Starting time: {}".format(START_TIME.strftime("%H:%M:%S")))
        print ("Ending time: {}".format(END_TIME.strftime("%H:%M:%S")))
        print ("Total execution time: {} milliseconds ({} seconds)".format(executionTime, (executionTime/1000)))
        print ("Total files downloaded: {}".format(len(downloadedFiles)))
        for file in downloadedFilesizes:
            print ("\tFilename: {}\t\tSize: {} bytes.".format(file['name'], file['size']))
        print ("=================================================================")

def loadCredentials(ftpPath):
    """
    Function that parses the configuration file and reads all the ftp credentials present in the file

    Parameters
    ----------
        - ftpPath : str
            Path to the ftp yaml file
    
    Returns
    -------
        - ftpConfigs : dict
            A dictionary of all FTP credentials present in the YAML path
            Each dictionary contains the host, name, password, and path to the directory to download from
    """
    localFrame = inspect.currentframe()
    with open(ftpPath, 'r') as stream:
        try:
            ftpConfigs = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            LOGGER.writeLog("Error while loading YAML.", localFrame.f_lineno, severity='code-breaker', data={'code':3, 'error':exc})

    # Check if each config is in proper order or lese remove the faulty configs
    for config in list(ftpConfigs.keys()):
        site = ftpConfigs[config]
        # Check if all four keys are present
        if not all(item in site.keys() for item in ['site', 'user', 'password', 'remote_path']):
            LOGGER.writeLog("Key missing from {} site info. Removing faulty config...".format(config), localFrame.f_lineno, severity='warning')
            del ftpConfigs[config]

        # Check if all four keys are not None
        if not (site['site'] and site['user'] and site['password'] and site['remote_path']):
            LOGGER.writeLog("A value in in {} site info is None (Not present). Removing faulty config...".format(config), localFrame.f_lineno, severity='warning')
            del ftpConfigs[config]
    return ftpConfigs

def connectToFTP(siteConfig, siteName, downloadPath):
    """
    Function that connects to the required FTP site, navigates to the specified path and hands over to the download function

    Parameters
    ----------
        - siteConfig : dict
            Dictionary that contains host, name, password, and path.
        - downloadPath : str
            Local machine's download path
    """
    localFrame = inspect.currentframe()

    hostname = siteConfig['site']
    username = siteConfig['user']
    password = str(siteConfig['password'])
    sourceDirectory = siteConfig['remote_path'] # TODO: change to camel case

    LOGGER.writeLog("Connecting to {} at host {}...".format(siteName, hostname), localFrame.f_lineno, severity='normal')

    # Attempt to connect        
    ftp = FTP(hostname)
    ftp.login(username, password)

    # Welcome could be multiple lines
    ftpWelcome = ftp.getwelcome()
    welcomeLines = []
    while True:
        try:
            oneline = ftpWelcome[:ftpWelcome.index('\n')]
            welcomeLines.append(oneline)
            ftpWelcome = ftpWelcome[ftpWelcome.index('\n')+1:]
        except ValueError:
            welcomeLines.append(ftpWelcome)
            break
    
    LOGGER.writeLog("Welcome: ", localFrame.f_lineno, severity='normal')
    for i in welcomeLines:
        LOGGER.writeLog(i, localFrame.f_lineno, severity='normal')
    LOGGER.writeLog("Connected Successfully!", localFrame.f_lineno, severity='normal')
    
    return downloadFiles(ftp, hostname, sourceDirectory, downloadPath)
    
def downloadFiles(ftp, hostname, sourceDirectory, localDownloadPath):
    """
    Function that downloads all the files present in the current working directory of the ftp connection to the local download path

    Parameters
    ----------
        - ftp : FTP Object
            FTP connection
        - hostname : str
            Hostname of the FTP site that the ftp object is connected to
        - sourceDirectory : str
            Path to the source directory in ftp server from where the files will be downloaded
        - localDownloadPath : str
            Local machine's path where the files need to be downloaded
    """
    localFrame = inspect.currentframe()

    ftp.cwd(sourceDirectory)
    LOGGER.writeLog("This script will only download files, not directories.", localFrame.f_lineno, severity='normal')
    LOGGER.writeLog("Files at {}:".format(sourceDirectory), localFrame.f_lineno, severity='normal')

    fileList = []
    ftp.retrlines("LIST", fileList.append)
    for i in fileList:
        LOGGER.writeLog(i, localFrame.f_lineno, severity='normal')

    # Get file list
    fileList = []
    ftp.retrlines("NLST", fileList.append)

    # Download each file
    filesDownloaded = []
    for filename in fileList:
        if (filename != '.') and (filename != '..'):
            LOGGER.writeLog("Downloading {}...".format(filename), localFrame.f_lineno, severity='normal')
            try:
                file = open(os.path.join(localDownloadPath, filename), "wb")
                ftp.retrbinary("RETR " + filename, file.write)
                filesDownloaded.append(filename)
                file.close()
            except Exception as directory_error:     # Could it be another error though?
                LOGGER.writeLog("{} was actually a directory, skipping...".format(filename), localFrame.f_lineno, severity='normal')

    LOGGER.writeLog("{} files successfully downloaded".format(len(filesDownloaded)), localFrame.f_lineno, severity='normal')

    disconnectFtp(ftp, hostname)

    return filesDownloaded

def disconnectFtp(ftp, hostname):
    """
    Function that disconnects from the ftp connection

    Parameters
    ----------
        - ftp : FTP Object
            FTP connection
        - hostname : str
            Hostname of the FTP site that the ftp object is connected to
    """
    localFrame = inspect.currentframe()
    LOGGER.writeLog("Disconnecting from {}...".format(hostname), localFrame.f_lineno, severity='normal')
    ftp.quit()
    LOGGER.writeLog("Disconnected from {}.".format(hostname), localFrame.f_lineno, severity='normal')
    time.sleep(1)

def unzipZippedFiles(downloadPath, downloadedFiles):
    """
    This function will read all the files that were downloaded, find the zip files, and unzip them

    Parameters
    ----------
        - downloadPath : str
            Local machine's path where the files were downloaded
        - downloadedFiles : list
            Name of the files that were downloaded

    """
    localFrame = inspect.currentframe()
    for i in downloadedFiles:
        file = os.path.join(downloadPath, i)

        # Check if file is zip file and unzip it
        if zipfile.is_zipfile(file):
            with zipfile.ZipFile(file, 'r') as zipObj:
                zipObj.extractall(downloadPath)
            LOGGER.writeLog("Unzipped {}.".format(file), localFrame.f_lineno, severity='normal')
        # Check if tar file
        elif tarfile.is_tarfile(file):
            tarFile = tarfile.open(file)
            tarFile.extractall(downloadPath) # specify which folder to extract to
            tarFile.close()
            LOGGER.writeLog("Unzipped {}.".format(file), localFrame.f_lineno, severity='normal')

""" Argument parsing part starts """
def parseArgs(argv):
    """
    Function that parses the arguments sent from the command line 
    and returns the behavioral variables to the caller.

    Parameters
    ----------
        - argv : str
            Arguments sent through the command line
    
    Returns
    -------
        - ftpYAMLPath : str
            A custom path to the configuration file containing API keys
        - outputFilePath : str
            A custom path to the location where the file needs to be downloaded. Must contain the file name as well.
        - verbose : bool
        - preserveOldFiles : bool
            A boolean variable that will tell the script to keep or remove older downloaded files in the download path
    """
    localFrame = inspect.currentframe()
    # Defining options in for command line arguments
    options = "hf:o:vpus:"
    long_options = ["help", "file=", 'output=', 'verbose', 'preserve', 'unzip', "site="]
    
    # Arguments
    ftpYAMLPath = 'ftp.yaml'
    customYAMLPathFoundAndValidated = False
    outputDIRPath = ''
    customOutputPathFoundAndValidated = False
    verbose = False
    preserveOldFiles = False
    unzipFiles = False
    targetSiteSpecified = False
    targetSite = '.*_.*'

    # Extracting arguments
    try:
        opts, args = getopt.getopt(argv, options, long_options)
    except getopt.GetoptError:
        # Not logging here since this is a command-line feature and must be printed on console
        LOGGER.verbose = True
        print ("Error in arguments!")
        print (HELP_MESSAGE)
        exit()

    for option, value in opts:
        if option == '-h':
            # Turn on verbose, print help message, and exit
            LOGGER.verbose = True
            print (HELP_MESSAGE)
            sys.exit()
        elif option in ("-f", "--file"):
            ftpYAMLPath = value
            customYAMLPathFoundAndValidated = validateConfigPath(ftpYAMLPath)
        elif option in ("-o", "--output"):
            outputDIRPath = value
            customOutputPathFoundAndValidated = validateDownloadPath(outputDIRPath)
        elif option in ("-p", "--preserve"):
            preserveOldFiles = True
        elif option in ("-v", "--verbose"):
            verbose = True
            # Updating logger's behavior based on verbose
            LOGGER.verbose = verbose
        elif option in ("-u", "--unzip"):
            unzipFiles = True
        elif option in ("-s", "--site"):
            targetSite = value
            targetSiteSpecified = True
            



    # If custom path to config file wasn't found, search in default locations
    if not customYAMLPathFoundAndValidated:
        ftpYAMLPath = getDefaultConfigPath()
    if not customOutputPathFoundAndValidated:
        outputDIRPath = getDefaultDownloadPath(preserve=preserveOldFiles)
    
    # Load credentials from the config path
    ftpConfigs = loadCredentials(ftpYAMLPath)
    
    # Validate the target site and make sure it is present in there
    if targetSiteSpecified:
        if not targetSite in ftpConfigs.keys():
            LOGGER.writeLog("Credentials of the target ftp site ({}) were not present in the config.".format(targetSite), localFrame.f_lineno, severity='code-breaker', data={'code':1})
            LOGGER.writeLog("Check the log to make sure that it wasn't removed due to incomplete infromation.", localFrame.f_lineno, severity='code-breaker', data={'code':1})
            LOGGER.writeLog("Exiting...", localFrame.f_lineno, severity='code-breaker', data={'code':1})
            exit()
    else:
        targetSite = ".*_.*"

    return ftpYAMLPath, outputDIRPath, preserveOldFiles, verbose, unzipFiles, ftpConfigs, targetSite

def validateConfigPath(configPath):
    """
    Function to validate the provided config file path.

    Parameters
    ----------
        - configPath : str
            Path to the configuration file
    Returns
    -------
        - validated : bool
            A True or False as a result of the validation of the path
    """
    localFrame = inspect.currentframe()
    # Check extension, must be YAML
    if not configPath.endswith('yaml'):
        LOGGER.writeLog("Configuration file must be .yaml extension. Looking for configuration file in default locations.", localFrame.f_lineno, severity='error')
        return False

    # Check if file exists
    if not os.path.exists(configPath):
        LOGGER.writeLog("Specified path to the configuration file is invalid. Looking for configuration file in default locations.", localFrame.f_lineno, severity='error')
        return False
    else:
        return True

def getDefaultConfigPath():
    """
    Function to validate the provided config file path.

    Returns
    -------
        - configPath : str
            Path to the configuration file if found in the default locations
    """
    localFrame = inspect.currentframe()
    fileName = 'ftp.yaml'
    
    # Check in current directory
    directory = os.getcwd()
    configPath = os.path.join(directory, fileName)
    if os.path.exists(configPath):
        return configPath
    
    # Check in alternative locations
    if sys.platform == 'win32' or sys.platform == 'win64': # Windows
        directory = os.path.expandvars(r'%LOCALAPPDATA%')
        configPath = os.path.join(directory, fileName)
        if os.path.exists(configPath):
            return configPath
    elif sys.platform == 'linux' or sys.platform == 'linux2': # Linux
        directory = expanduser('~')
        configPath = os.path.join(directory, fileName)
        if os.path.exists(configPath):
            return configPath
    else:
        LOGGER.writeLog("Platform couldn't be recognized. Are you sure you are running this script on Windows or Ubuntu Linux?", localFrame.f_lineno, severity='code-breaker', data={'code':1})
        exit()

    LOGGER.writeLog("ftp.yaml config file wasn't found in default locations! Specify a path to FTP credentials YAML file using (-f --file) argument.", localFrame.f_lineno, severity='code-breaker', data={'code':1})
    exit()

def validateDownloadPath(path):
    """
    Function that will validate the custom download path and load default if not found.

    Parameters
    ----------
        - path : str
            The custom download path that needs to be validated
    Returns
    -------
        - validated : bool
            True or False based on whether the path was validated or not
    """
    localFrame =  inspect.currentframe()
    # Check if path exists
    if not os.path.exists(path):
        LOGGER.writeLog("The download path does not exist. Switching to default download location.", localFrame.f_lineno, severity='warning')
        return False
    # Check if path is a directory
    if not os.path.isdir(path):
        LOGGER.writeLog("The download path must be a directory, not a file. Switching to default download location.", localFrame.f_lineno, severity='warning')
        return False
    return True

def getDefaultDownloadPath(preserve):
    """
    Function to check the operating system and determine the appropriate 
    download path for the export file based on operating system.

    This funciton also purges the whole directory with any previous export files.
    
    Returns
    -------
        - downloadPath : str
            A valid path that points to the diretory where the file should be downloaded
    """
    localFrame = inspect.currentframe()

    # If the platform is windows, set the download path to the current user's Downloads folder
    if sys.platform == 'win32' or sys.platform == 'win64': # Windows
        downloadPath = os.path.expandvars(r'%USERPROFILE%')
        downloadPath = os.path.join(downloadPath, 'Downloads')
        if not preserve:
            purge(downloadPath, 'SureDone_')
            LOGGER.writeLog("Purged existing files.", localFrame.f_lineno, severity='normal')
        return downloadPath

    # If Linux, set the download path to the $HOME/ folder
    elif sys.platform == 'linux' or sys.platform == 'linux2': # Linux
        downloadPath = expanduser('~')
        if not preserve:
            purge(downloadPath, 'SureDone_')
            LOGGER.writeLog("Purged existing files.", localFrame.f_lineno, severity='normal')
        return downloadPath

def purge(dir, pattern, inclusive=True):
    """
    A simple function to remove everything within a directory and it's subdirectories if the file name mathces a specific pattern.

    Parameters
    ----------
        - dir : str
            The top level path of the directory from where the searching will begin
        - pattern : regex-like str
            A regex-like string that defines the pattern that needs to be deleted
        - inclusive : boolean
            Currently only has a True implementation
    
    Returns
    -------
        - count : int
            The number files that were removed by the function
    """
    count = 0
    regexObj = re.compile(pattern)
    for root, dirs, files in os.walk(dir, topdown=False):
        for name in files:
            path = os.path.join(root, name)
            if bool(regexObj.search(path)) == bool(inclusive):
                if not path.endswith('.py'):
                    os.remove(path)
                    count += 1
    return count
""" Argument parsing part ends """

""" Custom logger class """
class Logger(object):
    """ The logger class that will handle all outputs, may it be console or log file. """
    def __init__(self, verbose=False):
        self.terminal = sys.stdout
        self.log = open(self.getLogPath(), "a")
        # Write the header row
        self.log.write(' Ind. |LineNo.| Time stamp  : Message')
        self.log.write('\n=====================================\n')
        self.verbose = verbose

    def getLogPath(self):
        """
        Function that will determine the default log file path based on the operating system being used.
        Will also create appropriate directories they aren't present.

        Returns
        -------
            - logFile : fileIO
                File IO for the whole script to log to.
        """
        # Define the file name for logging
        temp = datetime.now().strftime('%Y_%m_%d-%H-%M-%S')
        # Change this client name
        clientName = "test"
        logFileName = "ftp_dwonload_{}_{}.log".format(clientName, temp)

        # If the platform is windows, set the log file path to the current user's Downloads/log folder
        if sys.platform == 'win32' or sys.platform == 'win64': # Windows
            logFilePath = os.path.expandvars(r'%USERPROFILE%')
            logFilePath = os.path.join(logFilePath, 'Downloads')
            logFilePath = os.path.join(logFilePath, 'log')
            if os.path.exists(logFilePath):
                return os.path.join(logFilePath, logFileName)
            else:   # Create the log directory
                os.mkdir(logFilePath)
                return os.path.join(logFilePath, logFileName)

        # If Linux, set the download path to the $HOME/downloads folder
        elif sys.platform == 'linux' or sys.platform == 'linux2': # Linux
            logFilePath = expanduser('~')
            logFilePath = os.path.join(logFilePath, 'log')
            if os.path.exists(logFilePath):
                return os.path.join(logFilePath, logFileName)
            else:   # Create the log directory
                os.mkdir(logFilePath)
                return os.path.join(logFilePath, logFileName)

    def write(self, message):
        if self.verbose:
            self.terminal.write(message)
            self.terminal.flush()
        self.log.write(message)
    
    def writeLog(self, message, lineNumber, severity='normal', data=None):
        """
        Function that writes out to the log file and console based on verbose.
        The function will change behavior slightly based on severity of the message.

        Parameters
        ----------
            - message : str
                Message to write
            - severity : str
                Defines what the message is related to. Is the message:
                    - [N] : A 'normal' notification
                    - [W] : A 'warning'
                    - [E] : An 'error'
                    - [!] : A 'code-breaker error' (errors that are followed by the script exitting)
            - data : dict
                A dictionary that will contain additional information when a code-breaker error occurs
                Attributes:
                    - code : error code
                        1 : Generic error, only print the message.
                        3 : YAML loading error. Error object attached
                    - error : str
                        String produced by exception if an exception occured
        """
        # Get a timestamp
        timestamp = self.getCurrentTimestamp()

        # Format the message based on severity
        lineNumber = str(lineNumber)
        if severity == 'normal':
            indicator = '[N]'
            toWrite = ' ' + indicator + '  |  ' + lineNumber
            if int(lineNumber) < 100:
                toWrite += '   | '
            else:
                toWrite += '  | '
            toWrite += timestamp + ': ' + message
        elif severity == 'warning':
            indicator = '[W]'
            toWrite = ' ' + indicator + '  |  ' + lineNumber
            if int(lineNumber) < 100:
                toWrite += '   | '
            else:
                toWrite += '  | '
            toWrite += timestamp + ': ' + message
        elif severity == 'error':
            indicator = '[X]'
            toWrite = ' ' + indicator + '  |  ' + lineNumber
            if int(lineNumber) < 100:
                toWrite += '   | '
            else:
                toWrite += '  | '
            toWrite += timestamp + ': ' + message
        elif severity == 'code-breaker':
            indicator = '[!]'
            toWrite = ' ' + indicator + '  |  ' + lineNumber
            if int(lineNumber) < 100:
                toWrite += '   | '
            else:
                toWrite += '  | '
            toWrite += timestamp + ': ' + message
            
            if data['code'] == 2: # Response recieved but unsuccessful
                details = '\n[ErrorDetailsStart]\n' + data['response'] + '\n[ErrorDetailsEnd]'
                toWrite = toWrite + details
            elif data['code'] == 3: # YAML loading error
                details = '\n[ErrorDetailsStart]\n' + data['error'] + '\n[ErrorDetailsEnd]'
                toWrite = toWrite + details
        
        # Write out the message
        self.log.write(toWrite + '\n')
        if self.verbose:
            self.terminal.write(message + '\n')
            self.terminal.flush()

    def getCurrentTimestamp(self):
        """
        Simple function that calculates the current time stamp and simply formats it as a string and returns.
        Mainly aimed for logging.

        Returns
        -------
            - timestamp : str
                A formatted string of current time
        """
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def exceptionLogger(self, exctype, value, traceBack):
        """
        A simple printing function that will take place of the sys.excepthook function and print the results to the log instead of the console.

        Parameters
        ----------
            - exctype : object
                Exception type and details
            - Value : str
                The error passed while the exception was raised
            - traceBack : traceback object
                Contains information about the stack trace.
        """
        LOGGER.write('Exception Occured! Details follow below.\n')
        LOGGER.write('Type:{}\n'.format(exctype))
        LOGGER.write('Value:{}\n'.format(value))
        LOGGER.write('Traceback:\n')
        for i in traceback.format_list(traceback.extract_tb(traceBack)):
            LOGGER.write(i)

    def flush(self):
        # This flush method is needed for python 3 compatibility.
        # This handles the flush command by doing nothing.
        # You might want to specify some extra behavior here.
        pass

# Global variables
PYTHON_VERSION = float(sys.version[:sys.version.index(' ')-2])
LOGGER = Logger()

# It all starts here
if __name__ == "__main__":
    """
    Workflow:
    1. Tests to make sure you are using a minimum version of Python
    2. Gets and parses the arguments from the command-line execution.
    3. Creates a logger, logs in 2 places: log file and console.
    """
    sys.stdout = LOGGER
    sys.excepthook = LOGGER.exceptionLogger

    requiredPythonVersion = 3.5
    if not PYTHON_VERSION >= requiredPythonVersion:
        LOGGER.writeLog("Must use Python version 3.5 or higher! Currently using {}.".format(PYTHON_VERSION), localFrame.f_lineno, severity='code-breaker', data={'code':1})
        exit()
    
    main(sys.argv[1:])