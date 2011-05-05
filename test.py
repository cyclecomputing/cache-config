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

#   test.py <URL Prefix>
#
# Where <URL Prefix> would be the base URL for the CycleServer hosting the test
# plugins. Something like: http://localhost:8080/cycle/cache_config
#
# The test platform assumes that the plugins in the tests/plugins directory have
# been installed in a CycleServer instance.
#
# This can be done by symlinking the tests/plugins/cycle directory to "cycle"
# inside of CycleServer's plugins directory. Or by copying the files to the
# plugins directory for the CycleServer instance.


################################################################################
# IMPORTS
################################################################################

import os
import sys
import time
import subprocess
import re


################################################################################
# GLOBALS
################################################################################

# Keep track of files opened by tests
opened_files = {}


################################################################################
# CLASSES
################################################################################

class TestError(Exception):
    '''Error class for test runs.'''
    pass


################################################################################
# METHODS
################################################################################


def run(cmdLine):
    '''Run a command line executable and report it\'s output back.'''
    args = cmdLine.strip().split()
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    if p.returncode != 0:
        raise Exception("Error running " + cmdLine)
    return stdout.strip()


def runTest(site, test, defaultCache, **kwArgs):
    '''Run a test against a particular CycleServer instance using
    a particular cache file.'''
    print "Running test %s" % test

    opened_files["cache_file"] = True

    if os.path.exists("cache_file"):
        os.remove("cache_file")

    if defaultCache != None:
        fp = open("cache_file", "w")
        fp.write(defaultCache)
        fp.close()
        # set this to be a minute old so we always hit the site
        modtime = time.time() - 60
        os.utime("cache_file", (modtime, modtime))

    args = kwArgs.copy()
    if not args.has_key("fallback"):
        args["fallback"] = ""
    args["site"] = site
    args["test"] = test

    result = run("python cache_config.py cache_file 30 30 %(site)s/%(test)s %(fallback)s" % args)

    return result

def assertEquals(expected, actual, test):
    # normalize for Windows
    actual = re.sub(r'(\r\n|\r|\n)', '\n', actual)

    if expected != actual:
        raise TestError(test + ": Expected\n" + expected + "\nbut got\n" + actual)

def runTests(site):
    # success case (no initial cache)
    result = runTest(site, "success", None)
    assertEquals("Success\nLine2", result, "200 case")
                 
    # server error case (no initial cache)
    result = runTest(site, "error_nocache", None)
    assertEquals('CONFIG_FILE_ERROR="Exception updating config: HTTP Error 500: Internal Server Error"', 
                 result, "500 case")

    # server error case (no initial cache, fallback URL that works)
    result = runTest(site, "error_fallback", None, fallback=site + "/success")
    assertEquals('CONFIG_FILE_ERROR = "Exception updating config: HTTP Error 500: Internal Server Error"\n\nSuccess\nLine2', 
                 result, "500 case")

    # server error case (no initial cache, fallback URL that fails, second that works)
    result = runTest(site, "error_two_failures", None, fallback=site + "/error " + site + "/success")
    assertEquals('CONFIG_FILE_ERROR = "Exception updating config: HTTP Error 500: Internal Server Error; HTTP Error 500: Internal Server Error"\n\nSuccess\nLine2', 
                 result, "500 case")

    opened_files["alt_file"] = True
    fp = open("alt_file", "w")
    fp.write("Got from file")
    fp.close()

    # server error case (no initial cache, fallback URL that fails, then to file)
    result = runTest(site, "error_fallback_to_file", None, fallback=site + "/error file://" + os.path.abspath("alt_file"))
    assertEquals('CONFIG_FILE_ERROR = "Exception updating config: HTTP Error 500: Internal Server Error; HTTP Error 500: Internal Server Error"\n\nCONFIG_FILE_ERROR="Exception updating config: <urlopen error [Error 3] The system cannot find the path specified: \'\'>"', 
                 result, "500 case")

    # server error case (initial cache to use)
    result = runTest(site, "error_cache", 'Error Cached copy')
    assertEquals('CONFIG_FILE_ERROR="Exception updating config: HTTP Error 500: Internal Server Error"\n\nError Cached copy', 
                 result, "500 case")

    # auth requested case
    result = runTest(site, "auth", 'Auth Cached copy')
    assertEquals('CONFIG_FILE_ERROR="Exception updating config: HTTP Error 401: Unauthorized"\n\nAuth Cached copy', 
                 result, "auth case")

    # cached case, successfully in cache (but after requesting from the server, not in lieu of it)
    result = runTest(site, "not_modified/fresh", '304 Cached copy')
    assertEquals('304 Cached copy', result, "not-modified case (use cache)")

    # cached case, needs update
    result = runTest(site, "not_modified/stale", '304 Cached copy')
    assertEquals('Downloaded copy', result, "not-modified case (download)")

    # timeout requested case
    startTime = time.time()
    result = runTest(site, "timeout", 'Timeout Cached copy')
    runTime = time.time() - startTime
    expected = 2
    if runTime > expected + 1:
        raise TestError("Waited %f seconds for response; expected %s" % (runTime, expected))

    # should still have a good config
    assertEquals('CONFIG_FILE_ERROR="Exception updating config: <urlopen error timed out>"\n\nTimeout Cached copy', 
                 result, "timeout case")

    # re-run to make sure it works the second time without requesting
    startTime = time.time()
    result = run("python cache_config.py cache_file 30 30 %(site)s/%(test)s"
                 % { "site" : site, "test" : "timeout" })
                                                                                                         
    runTime = time.time() - startTime
    if runTime > 1:
        raise TestError("Second response should have been in the cache; took %s sec" % (runTime))

    # same result as before (error message is preserved)
    assertEquals('CONFIG_FILE_ERROR="Exception updating config: <urlopen error timed out>"\n\nTimeout Cached copy', 
                 result, "timeout case")

    # age the file so we hit the site again
    modtime = time.time() - 60
    os.utime("cache_file", (modtime, modtime))    

    # re-run to make sure error messages aren't accumulated
    startTime = time.time()
    result = run("python cache_config.py cache_file 30 30 %(site)s/%(test)s"
                 % { "site" : site, "test" : "timeout" })
                              
    runTime = time.time() - startTime
    if runTime < expected - 1:
        # here we WANT the timeout to make sure the code is trying again
        raise TestError("Only waited %s sec for site; expected timeout" % (runTime))

    # same result as before (error message is preserved but not duplicated)
    assertEquals('CONFIG_FILE_ERROR="Exception updating config: <urlopen error timed out>"\n\nTimeout Cached copy', 
                 result, "timeout case")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s SITE_PREFIX" % sys.argv[0]
        print "Install the plugins in the tests directory in a CycleServer instance."
        print "SITE_PREFIX is the path to the plugins (eg, http://localhost:8080/cycle/cache_config)"
        sys.exit(1)

    status = 0
    try:
        runTests(sys.argv[1])
        print "All tests ran successfully"
    except TestError, e:
        print "*** Test Failure:\n" + str(e)
        status = 1


    for k in opened_files.keys():
        if os.path.exists(k):
            os.remove(k)

    sys.exit(status)
