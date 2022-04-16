#!/usr/bin/env python

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

"""
run_mock_election.py - command line level script to merge CVR contest
branches into the master branch

See './run_mock_election.py -h' for usage information.

See ../docs/tech/run_mock_election.md for the context in which this
file was created.
"""

# Standard imports
# pylint: disable=wrong-import-position   # import statements not top of file
import os
import sys
import argparse
import logging
from logging import debug

# Local import
from common import Globals, Shellout
from address import Address
from election_config import ElectionConfig

# Functions


################
# arg parsing
################
# pylint: disable=duplicate-code
def parse_arguments():
    """Parse arguments from a command line"""

    parser = argparse.ArgumentParser(description=
    """run_mock_election.py will run a mock election with N ballots
    for a given town/GGO and the blank ballots contained within:

        - will randomly cast each blank ballot N times

        - will tally each of race and report the winner

    One basic idea is to run this in different windows, one per VTP
    scanner.  The scanner is nominally associated with a town (as
    configured).
    """,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    Address.add_address_args(parser, True)
    parser.add_argument("-i", "--iterations", type=int, default=10,
                            help="the number of unique blank ballots to cast")
    parser.add_argument("-t", "--towns",
        default="Alameda, 'Alum Rock', Berkeley, Evergreen, Milpitas, Oakland",
        help="the comma separated list of towns to cast ballots from")
    parser.add_argument("-s", "--state", default="California",
                            help="the state associated with the supplied towns (def=California)")
    parser.add_argument("-v", "--verbosity", type=int, default=3,
                            help="0 critical, 1 error, 2 warning, 3 info, 4 debug (def=3)")
    parser.add_argument("-n", "--printonly", action="store_true",
                            help="will printonly and not write to disk (def=True)")

    parsed_args = parser.parse_args()
    verbose = {0: logging.CRITICAL, 1: logging.ERROR, 2: logging.WARNING,
                   3: logging.INFO, 4: logging.DEBUG}
    logging.basicConfig(format="%(message)s", level=verbose[parsed_args.verbosity],
                            stream=sys.stdout)

    # Validate required args
    return parsed_args

################
# main
################
# pylint: disable=duplicate-code
def main():
    """Main function - see -h for more info"""

    # Create an VTP election config object
    the_election_config = ElectionConfig()
    the_election_config.parse_configs()

    # Note - this is a serial synchronous mock election loop.  A
    # parallel loop would have one VTP server git workspace somewhere
    # and N VTP scanner workspaces someplace else.  Depending on the
    # network topology, it is also possible to start up VTP scanner
    # workspaces on other machines as long as the git remotes and
    # clones are properly configured (with access etc).

    # While a mock election is running, it is also possible to use yet
    # another VTP scanner workspace to personally cast/insert
    # individual ballots for interactive purposes.

    # Assumes that each supplied town already has the blank ballots
    # generated and/or already committed.

    # Get list of available blank ballots
    blank_ballots = []
    with Shellout.changed_cwd(os.path.join(
        the_election_config.get('git_rootdir'), Globals.get('ROOT_ELECTION_DATA_SUBDIR'))):
        for dirpath, _, files in os.walk("."):
            for filename in [f for f in files if f.endswith(",ballot.json") \
                    and dirpath.endswith("blank-ballots/json") ]:
                blank_ballots.append(os.path.join(dirpath, filename))
    # Loop over the list N times
    for count in range(args.iterations):
        for blank_ballot in blank_ballots:
            debug(f"Iteration {count}, processing {blank_ballot}")
            # - cast a ballot
            Shellout.run(
                ['./cast_ballot.py', 'blank_ballot=' + blank_ballot],
                args.printonly)
            # - accept the ballot
            Shellout.run(
                ['./accept_ballot.py', 'ballot_ballot=' + blank_ballot],
                args.printonly)
            # - merge the ballot (first 100 will be a noop)
            Shellout.run(['./merge_ballot.py'], args.printonly)
    # merge the remaining contests
    Shellout.run(['./merge_ballot.py', '-f'], args.printonly)
    # tally the contests
    Shellout.run(['./tally_ballot.py'], args.printonly)

if __name__ == '__main__':
    args = parse_arguments()
    main()

# EOF