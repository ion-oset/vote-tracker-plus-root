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

"""Command line script to accept a ballot.

Run with '--help' for usage information.
"""

# Standard imports
import argparse
import sys

# Local imports
from vtp.core.address import Address
from vtp.core.common import Common
from vtp.ops.accept_ballot_operation import AcceptBallotOperation


def parse_arguments(argv):
    safe_args = Common.cast_thing_to_list(argv)
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Will run the git based workflow on a VTP scanner node to accept the json
rendering of the cast vote record of a voter's ballot. The json file is read,
the contests are extraced and submitted to separate git branches, one per
contest, and pushed back to the Voter Center's VTP remote.

In addition a voter's ballot receipt and offset are optionally printed.

Either the location of the ballot_file or the associated address is required.
""",
    )

    Address.add_address_args(parser, True)
    parser.add_argument(
        "-m",
        "--merge_contests",
        action="store_true",
        help="Will immediately merge the ballot contests (to main)",
    )
    parser.add_argument(
        "--cast_ballot",
        help="overrides an address - specifies a specific cast ballot",
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        type=int,
        default=3,
        help="0 critical, 1 error, 2 warning, 3 info, 4 debug (def=3)",
    )
    parser.add_argument(
        "-n",
        "--printonly",
        action="store_true",
        help="will printonly and not write to disk (def=True)",
    )

    return parser.parse_args(safe_args)


# pylint: disable=duplicate-code
def main():
    """Entry point for 'accept-ballot'."""

    args = parse_arguments(sys.argv[1:])
    op = AcceptBallotOperation(args)
    op.run()


# If called directly via this file
if __name__ == "__main__":
    main()
