#  VoteTrackerPlus
#   Copyright (C) 2022 Sandy Currier
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""How to manage a VTP specific contest"""

import json

class Contest:
    """A wrapper around the rules of engagement regarding a specific contest"""

    # Legitimate Contest keys.  Note 'selection' is not a legitimate
    # key for blank ballots
    _keys = ['candidates', 'question', 'tally', 'win-by', 'max', 'write-in',
                 'selection']

    @staticmethod
    def check_syntax(a_contest_blob):
        """
        Will check the synatx of a contest somewhat and conveniently
        return the name
        """
        name = next(iter(a_contest_blob))
        ### ZZZ - sanity check the name
        for key in a_contest_blob[name]:
            if key not in Contest._keys:
                raise KeyError(f"The specified key ({key}) is not a valid Contest key")
        return name

    def __init__(self, a_contest_blob, ggo, contests_index):
        """Boilerplate"""
        self.name = Contest.check_syntax(a_contest_blob)
        self.contest = a_contest_blob[self.name]
        self.ggo = ggo
        self.index = contests_index
        # set defaults
        if 'max' not in self.contest:
            if self.contest['tally'] == 'plurality':
                self.contest['max'] = 1
        # Some constructor time sanity checks
        if 'max' in self.contest and self.contest['max'] < 1:
            raise ValueError(f"Illegal value for max ({self.contest['max']}) "
                                 "- must be greater than 0")

    def __str__(self):
        """Boilerplate"""
        uber_contest = {'contest': self.contest, 'ggo': self.ggo, 'index': self.index,
                            'name': self.name}
        return json.dumps(uber_contest, sort_keys=True, indent=4, ensure_ascii=False)

    def get(self, name):
        """Generic getter - can raise KeyError"""
        # Return the choices
        if name == 'choices':
            if 'candidates' in self.contest:
                return self.contest['candidates']
            if 'question' in self.contest:
                return self.contest['question']
        # Return contest 'meta' data
        if name == 'name':
            return self.name
        if name == 'ggo':
            return self.ggo
        if name == 'index':
            return self.index
        # Else return contest data
        return getattr(self, 'contest')[name]

# EOF
