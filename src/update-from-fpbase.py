#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2109 Carnë Draug <carandraug+dev@gmail.com>
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

## Usage: update-from-fpbase OUTPUT_DIR FPBASE_DATA_FILE
##
## The data file is expected to be downloaded something like
## https://www.fpbase.org/api/proteins/spectra/?format=json

import collections
import dataclasses
import json
import os.path
import re
import sys
import typing


@dataclasses.dataclass
class FPSpectra:
    name: str
    slug: str
    ec: int # typing.Optional[int]
    qy: float #typing.Optional[float]
    excitation: list # typing.Sequence[typing.Sequence[float]]
    emission: list # typing.Sequence[typing.Sequence[float]]

    def __post_init__(self) -> None:
        for s in (self.excitation, self.emission):
            if any([len(p) != 2 for p in s]):
                raise ValueError()

    def to_spekcheck_format(self) -> str:
        ec = ' %d' % (self.ec) if self.ec is not None else ''
        qy = ' %f' % (self.qy) if self.qy is not None else ''
        header = ('## Type: dye\n'
                  '## Name: %s\n'
                  'Extinction coefficient:%s\n'
                  'Quantum Yield:%s\n'
                  'wavelength,absorption,emission\n'
                  % (self.name, ec, qy))

        ## FPbase had the spectra for excitation and emission separate
        ## so we have to join them for SPEKcheck.  We assume values
        ## outside the measured wavelengths are zero.  In most cases,
        ## there's excitation only values, then some overlap, and then
        ## only emission.  However, there are also cases (dKeima)
        ## where there is no overlap, just a gap between the two
        ## spectras.  There is also PSmOrange on the orange state
        ## where the excitation spectra data starts before and ends
        ## after the emission spectra data.  So while not as
        ## efficient, we just make dicts for all this.

        ex = {w : v for w, v in self.excitation}
        em = {w : v for w, v in self.emission}
        wls = sorted(set(ex.keys()) | set(em.keys()))
        data = ['%f,%f,%f' % (w, ex.get(w, 0.0), em.get(w, 0.0)) for w in wls]

        return header + '\n'.join(data) + '\n'


def parse_fpbase_entry(fpbase_entry: dict) -> typing.Sequence[FPSpectra]:
    ## Each FPbase entry corresponds to one protein.  In the case of a
    ## photoswitchable protein there's multiple states, and each state
    ## has its own spectra.
    ##
    ## In addition, for each state, FPbase has two spectras (em and
    ## ex) so we need to pair them correctly.

    entry_name = fpbase_entry['name']
    if len(fpbase_entry['spectra']) % 2:
        raise RuntimeError('unexpected odd number of spectras for %s'
                           % entry_name)

    ## The spectras are in a list with state being STATE_em or
    ## STATE_ex.  We need to pair them by STATE.
    spectras_by_state = collections.defaultdict(dict)
    for spectra in fpbase_entry['spectra']:
        state_name, ex_or_em = spectra['state'].rsplit('_', 1)
        if ex_or_em not in ['ex', 'em'] or state_name is None:
            raise RuntimeError()
        if (spectras_by_state.get(state_name) is not None
            and spectras_by_state[state_name].get(ex_or_em) is not None):
            raise RuntimeError('duplicated state')
        spectras_by_state[state_name][ex_or_em] = spectra

    spectras =[]
    for state_name, spectra_pair in spectras_by_state.items():
        if len(spectra_pair) != 2:
            raise RuntimeError()

        if len(spectras_by_state) == 1 and state_name == 'default':
            spectra_name = entry_name
            spectra_slug = fpbase_entry['slug']
        else:
            spectra_name = '%s (%s)' % (entry_name, state_name)
            ## The state name may not be safe for usage as slug.
            ## There is at least the case of rsFolder and and
            ## rsFolder2 where state can be 'Green (off)'.
            state_slug = re.sub('[^a-z0-9_]', '_', state_name.lower())
            spectra_slug = '%s_%s' % (fpbase_entry['slug'], state_slug)

        spectras.append(FPSpectra(name=spectra_name, slug=spectra_slug,
                                  ec=spectra_pair['ex']['ec'],
                                  qy=spectra_pair['em']['qy'],
                                  excitation=spectra_pair['ex']['data'],
                                  emission=spectra_pair['em']['data']))
    return spectras


def check_duplicated_attr(spectras: typing.Sequence[FPSpectra]) -> None:
    for attr in ['slug', 'name']:
        all_values = [getattr(x, attr) for x in spectras]
        if len(all_values) != len(set(all_values)):
            raise RuntimeError('some spectras have the same %s' % attr)


def main(argv):
    output_dir = argv[1]
    fpbase_data_fpath = argv[2]

    with open(fpbase_data_fpath, 'r') as fh:
        fpbase_data = json.load(fh)

    ## Each entry on the FPbase data may have multiple spectras, hence
    ## the for loop instead of list comprehension.
    spectras = []
    for fpbase_entry in fpbase_data:
        spectras.extend(parse_fpbase_entry(fpbase_entry))

    check_duplicated_attr(spectras)

    for spectra in spectras:
        ## Originally planned to use the slug for the filename but
        ## it's not nice on SPEKcheck.  So we use the name which
        ## mostly work.  The only issue so far is with '#' in
        ## 'Montipora sp. #20-9115'
        basename = re.sub('#', '', spectra.name)
        out_fpath = os.path.join(output_dir, basename + '.csv')
        with open(out_fpath, 'w') as fh:
            fh.write(spectra.to_spekcheck_format())


if __name__ == '__main__':
    main(sys.argv)
