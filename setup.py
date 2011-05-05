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

# This is the py2exe setup script. It tells py2exe how to convert this script
# in to a self-contained executable for running on Windows machines. You don't
# run this directly. It gets used during the build on Windows. For more
# information on what goes in to this file please see the py2exe documentation
# at:
#   http://www.py2exe.org/

from distutils.core import setup
import py2exe

setup(options = {"py2exe": {"dll_excludes": ["msvcr71.dll", 'w9xpopen.exe'], "compressed": 1,"optimize": 2,"ascii": 1,"bundle_files": 1}},
    zipfile = None,
    console=['cache_config.py'])
