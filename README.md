# CacheConfig

The cache_config tool is designed to work with HTCondor’s "Configuration with Pipes" feature, enabling users to fetch HTCondor configuration files from web servers, web applications or anything that can be represented using a URL.

It supports expiring, local file caching to reduce the number of calls triggered against a web service by a busy HTCondor system. This cache approach also decreases the latency for condor_* command line calls and ensures a HTCondor pool can survive an outage of all of the configuration-publishing resources.

Support for multiple URLs provides a simple mechanism to ensure high-availability for configuration information. The cache_config tool will attempt to pull configuration from each URL, stopping after the first successful pull happens.

## Installation

Download locations: 
    https://s3.amazonaws.com/download.cyclecomputing.com/cache-config/cache_config-1.2-win32.zip
    https://github.com/cyclecomputing/cache-config/releases/download/cache-config-1.2/cache_config-1.2-win32.zip

On Windows, put the cache_config.exe file in the HTCondor bin directory.

On other OSes, put the cache_config.py file in the HTCondor bin directory.

## Options

	cache_config.[exe|py] CacheFile CacheTTL LockTTL URL1 [URL2 ...]

* CacheFile - The file name for the cached config on local disk (in seconds)
* CacheTTL - The time-to-live for the cache file (in seconds)
* LockTTL - The time-to-live for the file lock (in seconds)
* URL1 - The first URL to check
* URL2, URL3, ... - Additional, optional failover URLs to check


## Lifecycle of a Cached Configuration

cache_config checks for an existing, local, cache file to determine whether the time-to-live (TTL) has expired. If the cache file's time to live has not expires, cache_config simply outputs the local, cache file contents. If the time to live for the cached file has expired, a cross-platform compatible lock is
acquired, with its own TTL to avoid deadlock cases. cache_config then gets the configuration file by attempting to read from the list of URLs for the configuration data. If any error occurs in reading from the first URL, the second is attempted, then the third, and so on, until configuration is successfully fetched and cached. Should all URLs fail, cache_config returns the existing, stale, configuration with additional configuration settings embedded in the output that publish the details of the failures.


## Installation


## HTCondor Configuration

In using cache_config with HTCondor it is recommended you copy it to your condor\bin directory (the BIN directory in your current HTCondor configuration). When configuring HTCondor, it is recommended you have a local configuration file that will get HTCondor up and running, then use the following line within that file to fetch the detailed configuration for the machine:

	LOCAL_CONFIG_FILE = "$(BIN)\cache_config.py $(LOCAL)\cached_config 30 30 http://webserver_url" |

The above line should appear last in your local configuration file to ensure that any configuration sent to HTCondor via the fetch URL overrides any of the local bootstrap configuration.

Note: If using cache_config for Windows replace `$(BIN)\cache_config.py` with `$(BIN)\cache_config.exe` in the configuration line above.


## Using `cache_config` with CycleServer

CycleServer stores associations between machines and configuration templates for easy machine-configuration management and serves up these configuration files up via a URL with a regular syntax. It has logic for choosing a default configuration template if a new, never-before-seen host requests configuration information.

To fetch your configuration from a CycleServer instance, make your configuration line:

	LOCAL_CONFIG_FILE = "$(BIN)\cache_config.py $(LOCAL)\cached_config 30 30 http://cycleserver_host:cycleserver_port/condor/assigned_template/$(FULL_HOSTNAME)" |


## See Also

* [HTCondor][htcondor] - high throughput computing from the University of Wisconsin
* For more information on "Configuration with Pipes" in HTCondor, please see the HTCondor manual. In the 8.0 manual the appropriate section is [3.3.1.4][configwithpipes]

## Copyright

Copyright (C) 2007-2013, Cycle Computing, LLC.

## License

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.  You may obtain a copy of the License at

<http://www.apache.org/licenses/LICENSE-2.0.txt>

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

[cycleserver]:http://www.cyclecomputing.com/cycleserver/overview
[htcondor]:http://research.cs.wisc.edu/htcondor
[curl]:http://curl.haxx.se/
[configwithpipes]:http://research.cs.wisc.edu/htcondor/manual/v8.0/3_3Configuration.html#SECTION00431400000000000000
