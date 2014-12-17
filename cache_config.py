#!/usr/bin/env python

###### COPYRIGHT NOTICE ########################################################
#
# Copyright (C) 2007-2011, Cycle Computing, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You may
# obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0.txt
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

################################################################################
# USAGE
################################################################################

# For detailed usage information please see README.txt
#
#   cache_config cacheFileName cacheFileTimeout lockTimeout URL1 [OptionalURL2 ...]
#
# The cache_config script requires the following arguments:
#   a cache file name to use for the final cache of the file
#   a time to live value for the cache file
#   a time to live value for the cache lock
#   one or more URLs to attempt to pull configuration from
#
# The cache_config script will attempt to pull an updated configuration for a machine
# from the URL list, stopping when it successfully pulls config from a URL. It will
# store the config on disk, with a time-to-live, and use the cached copy of the
# config if the time-to-live has not expired. It will keep using the cached copy if
# no new copy can be successfully fetched from any source on the URL list.


################################################################################
# IMPORTS
################################################################################
import sys
import os.path
import time
import urllib2
import shutil
import random
import logging
import socket



################################################################################
# GLOBALS
################################################################################

__version__ = "1.2"

# SOCKET CONFIGURATION
__timeout__ = 2 # seconds
socket.setdefaulttimeout(__timeout__)


# LOGGING CONFIGURATION
log_level_map      = dict()
log_level_map['1'] = logging.DEBUG
log_level_map['2'] = logging.INFO
log_level_map['3'] = logging.WARNING
log_level_map['4'] = logging.ERROR
log_level_map['5'] = logging.CRITICAL

env_var    = '_CACHE_TOOL_DEBUG'
should_log = os.environ.has_key(env_var) and log_level_map.has_key(os.environ[env_var])

if should_log:
    logLevel = log_level_map[os.environ[env_var]]
else:
    logLevel = logging.CRITICAL

logging.basicConfig(level=logLevel,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    stream=sys.stderr)

# PROXY CONFIGURATION
# Python http_proxy incompatibility for http_proxy:
#   handle the case where it does not start with http://
for http_proxy in ['http_proxy', 'HTTP_PROXY']:
    if os.environ.has_key(http_proxy) and os.environ[http_proxy][:7] != "http://":
        os.environ[http_proxy] = "http://"+os.environ[http_proxy]
        break

# SEED CONFIGURATION
random.seed()


################################################################################
# CLASSES
################################################################################

class DirectoryLockError(IOError):
    '''Error class for DirectorLock.'''
    # TBD Fill this in
    pass


class DirectoryLock:
    '''Platform-independent, directory-based, forceable locking mechanism.'''

    def __init__(self, directory_name, step_base=1, step_random_coeff=0.2):
        '''Create a directory-based lock and use the timeout to re-attempt the
        lock acquisition'''
        self.isLocked       = False
        self.dirName        = directory_name
        self.isStepRandom   = step_random_coeff == 0.0
        self.timeStep       = step_base*(1+(step_random_coeff*(1.0-2*random.random())))
        logging.info('Created a directory lock with timeStep %s seconds.' % str(self.timeStep))


    def acquire(self, acquire_by_force=True, lock_timeout=30):
        '''Attempt to acquire the lock, with a configuration timeout value. Return True if
        acquired. False if acquie was forced. Raises DirectoryLockError if directory is
        already locked.'''
        if lock_timeout <= 0:
            logmsg = "Error Acquiring DirectoryLock: '%s' with invalid timeout of '%d' seconds" % \
                    (self.dirName, lock_timeout)
            logging.error(logmsg)
            raise DirectoryLockError(logmsg)

        if self.isLocked == True:
            logmsg = "Error Acquiring DirectoryLock: '%s' is already locked!" % self.dirName
            logging.error(logmsg)
            raise DirectoryLockError(logmsg)

        wait_duration = 0
        logging.info("Acquiring lock")

        while wait_duration < lock_timeout:
            wait_duration += self.timeStep
            try:
                if os.path.isdir(self.dirName):
                    logging.info("Lock directory exists")
                    raise os.error
                else:
                    logging.info("Creating lock directory")
                    os.mkdir(self.dirName)
            except os.error, err:
                logging.info("Lock directory exists sleeping.")
                time.sleep(self.timeStep)
            else:
                logging.info("Successfully acquired the lock.")
                self.isLocked = True
                return True

        if acquire_by_force:
            logging.warning("Acquiring lock by force")
            self.isLocked = True
            return False
        else:
            logmsg = "Error acquiring DirectoryLock on '%s'" % self.dirName
            logging.error(logmsg)
            raise DirectoryLockError(logmsg)


    def __del__(self):
        '''Automatically destroy the lock when the object is deleted.'''
        if self.isLocked:
            self.release(True)

         
    def release(self, raise_remove_error=False):
        '''Release the lock. Raises DirectoryLockError if lock cannot be removed
        or does not exist.'''
        if not self.isLocked:
            logmsg = "Error releasing DirectoryLock: '%s' is not locked yet!" % self.dirName
            logging.error(logmsg)
            raise DirectoryLockError(logmsg)
        self.isLocked = False
        try:
            os.rmdir(self.dirName)
        except os.error, err:
            if raise_remove_error:
                logmsg = "Error releasing DirectoryLock: '%s' remove appeared to fail!" % self.dirName
                logging.error(logmsg)
                raise DirectoryLockError(logmsg)


class CacheConfigFile:
    '''An object representation of a config cache file. Provides some utility
    functions for dealing with cached configs on disk.'''

    def __init__(self, filename, ttl=30):
        self.fileName     = filename
        self.fileTTL      = ttl
        randStr           = '.'+hex(int(random.random()*256*256*256*256))[2:10]
        self.tempFileName = filename+randStr
        logging.info("CacheConfigFile created with tempFileName: %s"%self.tempFileName)

    def __del__(self):
        '''Clean up any temporary files that were created.'''
        if os.path.isfile(self.tempFileName):
            os.remove(self.tempFileName)

    def temporaryFileName(self):
        '''Return the name of a unique, temporary file we can use.'''
        return self.tempFileName

    def exists(self):
        '''Returns True if the cache file exists on disk, otherwise False.'''
        return os.path.exists(self.fileName)

    def shouldUpdate(self):
        '''Check the cache file\'s timestamp against the TTL value for this file
        set when the object was created. Return True if the TTL has expired.
        Otherwise False.'''
        currentTime = time.time()
        if self.exists():
            lastModified = os.path.getmtime(self.fileName)

            logging.info("CacheConfigFile last modified: %s" % lastModified)
            cacheAge = currentTime-lastModified
            logging.info("CacheConfigFile age: %s" % cacheAge)
            if cacheAge < float(self.fileTTL):
                logging.info("CacheConfigFile can be reused!")
                return False
        logging.info("CacheConfigFile should be updated!")
        return True


class CustomHttpHandler(urllib2.HTTPHandler):
    '''Handler helper class for dealing with URL requests.'''

    def http_error_304(self, req, fp, code, msg, hdrs):
        return open(self.cache_file)



################################################################################
# METHODS
################################################################################

def writeToFile(in_fp, out_fp, error):
    '''Copy bits from in_fp to out_fp, keeping track of an errors encountered
    along the way. Closes in_fp at the end. Returns the contents of in_fp as
    a single string, which may include error messages encountered during writing.
    Error messages are written out as a Condor config variable in the config
    stream named CONFIG_FILE_ERROR.'''
    # Track errors encountered
    config_lines = []

    try:
        if error:
            config_lines.append(error)
        current_line = in_fp.readline()
        skip_next = False
        while current_line != '':
            if skip_next:
                # skip this line but not the one after this
                skip_next = False
            elif error != None and current_line.find("CONFIG_FILE_ERROR") != -1:
                # do nothing on this line, and skip the next blank line too
                skip_next = True
            else:
                config_lines.append(current_line)
            current_line = in_fp.readline()

        config = ''.join(config_lines)
        out_fp.write(config)
        return config
    finally:
        in_fp.close()



def downloadConfig(url, cache_file, temp_cache_file_fp, lastAttempt):
    '''Fetch a config using a URL as the source for the config and
    cache it locally on disk. Returns the full contents of the config
    file on success. Raises an Exception if there is a problem
    downloading the contents.'''
    handler            = CustomHttpHandler()
    handler.cache_file = cache_file
    opener             = urllib2.build_opener(handler)
    opener.addheaders = [('User-agent', 'CacheConfig/%s' % __version__)]
    urllib2.install_opener(opener)

    try:
        req = urllib2.Request(url=url)
        if os.path.exists(cache_file):
            # Tell the server about the last time we got the file. It may
            # elect to return a no-change message if the config hasn't
            # actually changed. Saving us time moving data over the wire.
            modified = time.gmtime(os.path.getmtime(cache_file))
            RFC_1123_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"
            req.add_header("If-Modified-Since", time.strftime(RFC_1123_FORMAT, modified))
        url_fp = urllib2.urlopen(req, timeout=15)
        config = writeToFile(url_fp, temp_cache_file_fp, False)
    except Exception, e:
        if not lastAttempt:
            raise e
        # Reuse the cached copy but add an error message to file in the
        # form of a Condor configuration attribute named CONFIG_FILE_ERROR.
        error = 'CONFIG_FILE_ERROR="Exception updating config: %s"\n\n' % str(e)
        in_fp = None
        if os.path.exists(cache_file):
            in_fp  = open(cache_file, "rU")
            config = writeToFile(in_fp, temp_cache_file_fp, error)
        else:
            config = error
    return config


def main():
    '''The main() routine that drives the script.'''
    if len(sys.argv) > 4:
        try:
            logging.info("Parsing Arguments...")
            cache_file_name    = sys.argv[1]
            cache_file_timeout = int(sys.argv[2])
            cache_lock_timeout = int(sys.argv[3])
            cache_config_file  = CacheConfigFile(cache_file_name, cache_file_timeout)
            config_urls        = sys.argv[4:]
            logging.debug("CacheFile Name: %s\nCacheFile TTL: %d\nLock TTL: %d\n" % \
                    (cache_file_name, cache_file_timeout, cache_lock_timeout))
            for u in config_urls:
                logging.debug("Config URL: %s" %u)
        except:
            logging.error("Error parsing arguments...")
            return 1

        try:
            # Generate an app-specific directory name for our lock and then
            # attempt to get a lock on it.
            directoryName = cache_config_file.fileName + '_'
            dlock         = DirectoryLock(directoryName)
            dlock.acquire(True, cache_lock_timeout)
        except DirectoryLockError, error:
            logging.error("Error acquiring directory lock: %s" % error)
            pass

        config         = None
        should_print   = False
        error_occurred = False
        error_messages = []

        # Once acquired, if cachefile doesn't exist or it is beyond its time to live (TTL),
        # request the configuration file from the URL given. One the configuration has been
        # fetched withou error, write it to temporary file and then move it in to place .
        should_update = cache_config_file.shouldUpdate()
        if should_update:
            url_counter = 0
            # Keep moving through the URLs in the list until we can pull a configuration
            while should_print == False and url_counter < len(config_urls):       
                try:
                    error_occurred = False
                    logging.info("Opening temp cache file: %s" % \
                            cache_config_file.temporaryFileName())
                    temp_cache_file_fp = open(cache_config_file.temporaryFileName(), 'w')
                    try:
                        logging.info("Opening URL #%d: %s" % \
                                (url_counter+1, config_urls[url_counter]))
                        lastAttempt = url_counter == len(config_urls) - 1
                        config = downloadConfig(config_urls[url_counter], \
                                cache_config_file.fileName, temp_cache_file_fp, lastAttempt)
                    finally:
                        temp_cache_file_fp.close()
                    logging.info("Copying tempCacheConfig file to cacheFile")
                    shutil.copy(cache_config_file.temporaryFileName(), cache_config_file.fileName)
                    logging.info("Removing tempCacheConfig file")
                    os.remove(cache_config_file.temporaryFileName())
                    should_print = True
                except Exception, e:
                    config         = None
                    error_occurred = True
                    error_messages.append(str(e))
                    logging.error("Exception updating config: %s" % e)
                    try:
                        os.remove(cache_config_file.temporaryFileName())
                    except:
                        pass
                url_counter += 1
        
        if len(error_messages) > 0:
            print 'CONFIG_FILE_ERROR = "Exception updating config: ' + "; ".join(error_messages) + '"\n'
        # If an error occurred updating the cache or we didn't need to update the
        # cache file then read it. By not deleting the existing cache from disk before
        # we've successfully cached the new version, it ensures we can always fall
        # back on a stale, but correct configuration for the machine even if all
        # of our config sources are offline.
        if error_occurred or not should_update:
            logging.info("Reusing the existing cached config file")
            try:
                error_occurred = False
                cache_fp       = open(cache_config_file.fileName, 'rU')
                config         = cache_fp.read()
                cache_fp.close()
                should_print   = True
            except:
                error_occurred = True

        if should_log:
            # If we are logging, give the user a chance to read the output.
            time.sleep(5)

        if should_print and not error_occurred:
            print config
    else:
        # Print out usage information, but do it in the form of valid Condor
        # configuration syntax so Condor isn't crashed by incorrect use of
        # this tool.
        print 'APPLICATION = "cache_config v%s"' % __version__
        print 'ARGUMENTS = "cache_config CACHE CACHE_TTL LOCK_TTL URL1 [URL2 ...]"'
        print 'CACHE_CONFIG_COPYRIGHT = "Cycle Computing, LLC 2007 -"'


if __name__ == '__main__':
    '''Run the main method if we are being called as a script.'''
    sys.exit(main())
