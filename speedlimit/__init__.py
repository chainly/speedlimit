#coding: utf8
"""
@Ctime 2017-09-22 19:20:07
@Mtime 2017-09-22 19:20:11
@Author COOl(1258626769@qq.com)
@Ref: https://github.com/harlowja/speedlimit/blob/master/speedlimit/__init__.py
    https://en.wikipedia.org/wiki/Token_bucket
    http://lartc.org/lartc.html#AEN690
    processbar
The token bucket algorithm can be conceptually understood as follows:

A token is added to the bucket every {\displaystyle 1/r} 1/r seconds.
The bucket can hold at the most {\displaystyle b} b tokens. If a token arrives when the bucket is full, it is discarded.
When a packet (network layer PDU) of n bytes arrives, n tokens are removed from the bucket, and the packet is sent to the network.
If fewer than n tokens are available, no tokens are removed from the bucket, and the packet is considered to be non-conformant.

@Next: make _bucket <= init_bucket
    make min independent
"""

# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import math
import time
import socket
class TooSlowError(socket.error):
    pass

# http://www.cnblogs.com/memo-store/p/5658277.html
from monotonic import monotonic as _now


class SpeedLimit(object):
    """Speed/limiting iterator wrapper object.
    A wrapper object that uses the `token bucket`_ algorithm to limit the
    rate at which values comes out of an iterable. This can be used to limit
    the consumption speed of iteration of some other iterator (or iterable).
    .. _token bucket: http://en.wikipedia.org/wiki/Token_bucket
    """
    def __init__(self,
                 # How many items to yield from the provided
                 # wrapped iterator (per second).
                 items_per_second=0,
                 # Used to simulate a thread with its own 'tic rate'. Making
                 # this smaller affects the accuracy of the 'tic' calculation,
                 # which affects the accuracy of consumption (and delays).
                 refresh_rate_seconds=1,
                 # length of the bucket
                 initial_bucket_size=1,
                 # min or raise
                 min_per_second=0,
                 check_interval=5,
                 too_slow_count=10, 
                 # Made a keyword argument, so one could replace this
                 # with a eventlet.sleep or other idling function...
                 sleep_func=time.sleep):
        # unset items_per_second to not limit
        if not items_per_second:
            items_per_second = 10**10 # 10GB
        assert min_per_second <= items_per_second, 'min > max!'
        
        self._refresh_rate_seconds = refresh_rate_seconds
        self._bucket = (items_per_second *
                        refresh_rate_seconds * initial_bucket_size)
        self._items_per_tic = items_per_second * refresh_rate_seconds
        self._next_fill = _now() + refresh_rate_seconds
        self._sleep = sleep_func
        
        # min
        # unset min_per_second to not raise
        if not min_per_second:
            check_interval = 10**10 # to long
            
        self._last_check = _now()
        self._last_size = self._bucket
        self._check_interval = check_interval
        self._max_left_per_second = (items_per_second-min_per_second) * initial_bucket_size
        self._slow_count = 0
        self._too_slow_count = too_slow_count

    def _check_fill(self):
        # Fill the bucket based on elapsed time.
        #
        # This simulates a background thread...
        now = _now() 
        if now > self._next_fill:
            d = now - self._next_fill
            tics = int(math.ceil(d / self._refresh_rate_seconds))
            self._bucket += tics * self._items_per_tic
            self._next_fill += tics * self._refresh_rate_seconds
            
        if now - self._last_check > self._check_interval:
            _d = now - self._last_check
            _max_left = self._last_size + self._max_left_per_second * _d
            if self._bucket > _max_left:
                self._slow_count += 1
                print('*TooSlow %s*, %s > %s' % (self._slow_count, self._bucket ,_max_left))
                if self._slow_count >= self._too_slow_count:
                    raise TooSlowError('%s>%s' % (self._bucket, _max_left))
            self._last_size = self._bucket  
            self._last_check = now        

    def speed_limit_iter(self, itr, chunk_size_cb=len):
        """Return an iterator/generator which limits after each iteration.
        :param itr: an iterator to wrap
        :param chunk_size_cb: a function that can calculate the
                              size of each chunk (if none provided this
                              defaults to 1)
        """
        for chunk in itr:
            if chunk_size_cb is None:
                sz = 1
            else:
                sz = chunk_size_cb(chunk)
            self._check_fill()
            if sz > self._bucket:
                now = _now()
                tics = int((sz - self._bucket) / self._items_per_tic)
                tm_diff = self._next_fill - now
                secs = tics * self._refresh_rate_seconds
                if tm_diff > 0:
                    secs += tm_diff
                self._sleep(secs)
                self._check_fill()
            self._bucket -= sz
            yield chunk
            
            
if __name__ == '__main__':
    import urllib2
    url = 'http://sw.bos.baidu.com/sw-search-sp/software/d28b12c330f7b/android-studio-bundle_2.2.0.0.exe'
    
    fp = urllib2.urlopen(url)
    police = SpeedLimit(min_per_second=10000000, check_interval=2,)
    
    for alpha in police.speed_limit_iter(fp):
        print(police._bucket, _now(), police._last_size, police._slow_count,)
        print(len(alpha))
    
