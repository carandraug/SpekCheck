#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2018 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## SpekCheck is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## SpekCheck is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with SpekCheck.  If not, see <http://www.gnu.org/licenses/>.

import errno
import json
import os
import os.path
import shutil
import sys

def parse_filter(filt):
    parts = (filt.strip()).rsplit(' ', 1)
    if len(parts) == 1:
        parts.append('t') # default to transmission
    filt = {
        'name' : parts[0].strip(),
        'mode' : (parts[1].strip()).lower(),
    }
    if filt['mode'] not in ('r', 't'):
        raise RuntimeError("filter '%s' mode '%s' not 'r' or 't'"
                           % (filt['name'], filt['mode']))
    return filt

def parse_setup_line(line):
    ## The line format is as follow:
    ##
    ##  name, dye, excitation source, filter1, filter2 :: filter3 filter4
    ##
    ## Some of the fields may be empty (except the name), and any
    ## number of filters is possible.  The '::' splits emission
    ## from excitation filters.  In addition, each filter will be
    ## of the format:
    ##
    ##    filter_name mode
    ##
    ## where mode is an R (reflection) or T (transmission)
    setup_parts = [x.strip() for x in line.split(',')]
    name = setup_parts[0]
    dye = setup_parts[1]
    ex_source = setup_parts[2]

    ex_filters = []
    em_filters = []
    ex_path = True # looking at filters in ex path until we see '::'
    for filt in setup_parts[3:]:
        c_idx = filt.find('::')
        if c_idx >= 0:
            if not ex_path:
                raise RuntimeError("more than one '::' in set '%s'"
                                   % (name))
            ex_filters.append(parse_filter(filt[:c_idx]))
            ex_path = False
            em_filters.append(parse_filter(filt[c_idx+2:]))

        elif ex_path: # still looking at ex filters
            ex_filters.append(parse_filter(filt))
        else: # already looking at em filters
            em_filters.append(parse_filter(filt))

    setup = {
        'name' : setup_parts[0],
        'dye' : setup_parts[1],
        'ex_source' : setup_parts[2],
        'ex_filters' : ex_filters,
        'em_filters' : em_filters,
    }
    return setup


class API(object):
    def __init__(self, api_dir, version):
        self._dirpath = os.path.join(api_dir, 'v' + version)
        self._version = version

    def reset(self):
        """Remove the whole directory tree and recreate it a new
        """
        try:
            shutil.rmtree(self._dirpath)
        except OSError as err:
            if err.errno == errno.ENOENT:
                pass
            else:
                raise
        try:
            os.makedirs(self._dirpath)
        except OSError as err:
            if err.errno == errno.EEXIST:
                pass
            else:
                raise

    def create(self, data_dir):
        """Create API dir anew from data in a directory.
        """
        setups = []
        with open(os.path.join(data_dir, 'sets'), 'r') as fh:
            for line in fh:
                line = line.strip()
                if line.startswith('//') or len(line) == 0:
                    continue # skip comments and empty lines
                setups.append(parse_setup_line(line))

        with open(os.path.join(self._dirpath, 'sets'), 'w') as fh:
            json.dump(setups, fp=fh)

def main(data_dir, api_dir, version):
    api = API(api_dir, version)
    api.reset()
    api.create(data_dir)

if __name__ == '__main__':
    main(*sys.argv[1:])
