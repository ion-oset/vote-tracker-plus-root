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

See ../../docs/tech/run_mock_election.md for the context in which this
file was created.
"""

# Standard imports
# pylint: disable=wrong-import-position   # import statements not top of file
import argparse
import logging
import os
import sys
import time

# Local import
from vtp.utils.address import Address
from vtp.utils.ballot import Ballot
from vtp.utils.common import Globals, Shellout
from vtp.utils.election_config import ElectionConfig

# Functions

################
# arg parsing
################
# pylint: disable=duplicate-code
def parse_arguments():
    """Parse arguments from a command line"""

    parser = argparse.ArgumentParser(
        description="""Will run a mock election with N ballots
    across the available blank ballots found in the ElectionData.

    One basic idea is to run this in different windows, one per VTP
    scanner.  The scanner is nominally associated with a town (as
    configured).

    When "-d scanner" is supplied, run_mock_election.py will randomly
    cast and scan ballots.

    When "-d server" is supplied, run_mock_election.py will
    synchronously run the merge_contests.py program which will once
    every 10 seconds.  Note that nominally 100 contgests need to have
    been pushed for merge_contests.py to merge in a contest into the
    master branch without the --flush_mode option.

    If "-d both" is supplied, run_mock_election.py will run a single
    scanner N iterations while also calling the server function.  If
    --flush_mode is set to 1 or 2, run_mock_election.py will then
    flush the ballot cache before printing the tallies and exiting.

    By default run_mock_election.py will loop over all available blank
    ballots found withint the ElectionData tree.  However, either a
    specific blank ballot or an address can be specified to limit the
    mock to a single ballot N times.
    """
    )

    Address.add_address_args(parser)
    parser.add_argument(
        "--blank_ballot",
        help="overrides an address - specifies the specific blank ballot",
    )
    parser.add_argument(
        "-d",
        "--device",
        default="",
        help="specify a specific VC local device (scanner or server or both) to mock",
    )
    parser.add_argument(
        "-m",
        "--minimum_cast_cache",
        type=int,
        default=100,
        help="the minimum number of cast ballots required prior to merging (def=100)",
    )
    parser.add_argument(
        "-f",
        "--flush_mode",
        type=int,
        default=0,
        help="will either not flush (0), flush on exit (1), or flush on each iteration (2)",
    )
    parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=10,
        help="the number of unique blank ballots to cast (def=10)",
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

    parsed_args = parser.parse_args()
    verbose = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
        4: logging.DEBUG,
    }
    logging.basicConfig(
        format="%(message)s", level=verbose[parsed_args.verbosity], stream=sys.stdout
    )

    # Validate required args
    if parsed_args.device not in ["scanner", "server", "both"]:
        raise ValueError(
            "The --device parameter only accepts 'device' or 'server' "
            f"or 'both' - ({parsed_args.device}) was suppllied."
        )
    if parsed_args.flush_mode not in [0, 1, 2]:
        raise ValueError(
            "The value of flush_mode must be either 0, 1, or 2"
            f" - {parsed_args.flush_mode} was supplied."
        )
    return parsed_args


def scanner_mockup(the_election_config, ballot):
    """Simulate a VTP scanner"""

    election_data_dir = os.path.join(
        the_election_config.get("git_rootdir"), Globals.get("ROOT_ELECTION_DATA_SUBDIR")
    )
    merge_contests = Shellout.get_script_name("merge_contests.py", the_election_config)
    tally_contests = Shellout.get_script_name("tally_contests.py", the_election_config)
    cast_ballot = Shellout.get_script_name("cast_ballot.py", the_election_config)
    accept_ballot = Shellout.get_script_name("accept_ballot.py", the_election_config)

    # Get list of available blank ballots
    blank_ballots = []
    if ballot:
        # a blank ballot location was specified (either directly or via an address)
        blank_ballots.append(ballot)
    else:
        with Shellout.changed_cwd(election_data_dir):
            for dirpath, _, files in os.walk("."):
                for filename in [
                    f
                    for f in files
                    if f.endswith(",ballot.json")
                    and dirpath.endswith("blank-ballots/json")
                ]:
                    blank_ballots.append(os.path.join(dirpath, filename))
    # Loop over the list N times
    if not blank_ballots:
        raise ValueError("found no blank ballots to cast")

    for count in range(ARGS.iterations):
        for blank_ballot in blank_ballots:
            logging.debug(
                "Iteration %s of %s - processing %s",
                count,
                ARGS.iterations,
                blank_ballot,
            )
            # - cast a ballot
            #            import pdb; pdb.set_trace()
            with Shellout.changed_cwd(election_data_dir):
                Shellout.run(
                    ["git", "pull"],
                    printonly=ARGS.printonly,
                    verbosity=ARGS.verbosity,
                    no_touch_stds=True,
                    timeout=None,
                    check=True,
                )
            Shellout.run(
                [
                    cast_ballot,
                    "--blank_ballot=" + blank_ballot,
                    "--demo_mode",
                    "-v",
                    ARGS.verbosity,
                ],
                printonly=ARGS.printonly,
                no_touch_stds=True,
                timeout=None,
                check=True,
            )
            # - accept the ballot
            Shellout.run(
                [
                    accept_ballot,
                    "--cast_ballot=" + Ballot.get_cast_from_blank(blank_ballot),
                    "-v",
                    ARGS.verbosity,
                ],
                printonly=ARGS.printonly,
                no_touch_stds=True,
                timeout=None,
                check=True,
            )
            if ARGS.device == "both":
                # - merge the ballot's contests
                if ARGS.flush_mode == 2:
                    # Since casting and merging is basically
                    # synchronous, no need for an extra large timeout
                    Shellout.run(
                        [merge_contests, "-f", "-v", ARGS.verbosity],
                        printonly=ARGS.printonly,
                        no_touch_stds=True,
                        timeout=None,
                        check=True,
                    )
                else:
                    # Should only need to merge one ballot worth of
                    # contests - also no need for an extra large
                    # timeout
                    Shellout.run(
                        [
                            merge_contests,
                            "-m",
                            ARGS.minimum_cast_cache,
                            "-v",
                            ARGS.verbosity,
                        ],
                        printonly=ARGS.printonly,
                        no_touch_stds=True,
                        timeout=None,
                        check=True,
                    )
                # don't let too much garbage build up
                if count % 10 == 9:
                    Shellout.run(
                        ["git", "gc"],
                        printonly=ARGS.printonly,
                        verbosity=ARGS.verbosity,
                        no_touch_stds=True,
                        timeout=None,
                        check=True,
                    )
    if ARGS.device == "both":
        # merge the remaining contests
        # Note - this needs a longer timeout as it can take many seconds
        Shellout.run(
            [merge_contests, "-f", "-v", ARGS.verbosity],
            printonly=ARGS.printonly,
            no_touch_stds=True,
            timeout=None,
            check=True,
        )
        # tally the contests
        Shellout.run(
            [tally_contests, "-v", ARGS.verbosity],
            printonly=ARGS.printonly,
            no_touch_stds=True,
            timeout=None,
            check=True,
        )
    # clean up git just in case
    Shellout.run(
        ["git", "gc"],
        printonly=ARGS.printonly,
        verbosity=ARGS.verbosity,
        no_touch_stds=True,
        timeout=None,
        check=True,
    )


def server_mockup(the_election_config):
    """Simulate a VTP server"""
    # This is the VTP server simulation code.  In this case, the VTP
    # scanners are pushing to an ElectionData remote and this (server)
    # needs to pull from the ElectionData remote.  And, in this case
    # the branches to be merged are remote and not local.
    start_time = time.time()
    # Loop for a day and sleep for 10 seconds
    seconds = 3600 * 24
    election_data_dir = os.path.join(
        the_election_config.get("git_rootdir"), Globals.get("ROOT_ELECTION_DATA_SUBDIR")
    )

    merge_contests = Shellout.get_script_name("merge_contests.py", the_election_config)
    tally_contests = Shellout.get_script_name("tally_contests.py", the_election_config)
    while True:
        with Shellout.changed_cwd(election_data_dir):
            Shellout.run(
                ["git", "pull"],
                ARGS.printonly,
                ARGS.verbosity,
                no_touch_stds=True,
                timeout=None,
                check=True,
            )
        if ARGS.flush_mode == 2:
            Shellout.run(
                [merge_contests, "-r", "-f", "-v", ARGS.verbosity],
                printonly=ARGS.printonly,
                no_touch_stds=True,
                timeout=None,
                check=True,
            )
            Shellout.run(
                [tally_contests, "-v", ARGS.verbosity],
                printonly=ARGS.printonly,
                no_touch_stds=True,
                timeout=None,
                check=True,
            )
            return
        Shellout.run(
            [merge_contests, "-r", "-m", ARGS.minimum_cast_cache, "-v", ARGS.verbosity],
            printonly=ARGS.printonly,
            no_touch_stds=True,
            timeout=None,
            check=True,
        )
        logging.info("Sleeping for 10")
        time.sleep(10)
        elapsed_time = time.time() - start_time
        if elapsed_time > seconds:
            break
    if ARGS.flush_mode in [1, 2]:
        print("Cleaning up remaining unmerged ballots")
        Shellout.run(
            [merge_contests, "-r", "-f", "-v", ARGS.verbosity],
            printonly=ARGS.printonly,
            no_touch_stds=True,
            timeout=None,
            check=True,
        )
    # tally the contests
    Shellout.run(
        [tally_contests, "-v", ARGS.verbosity],
        printonly=ARGS.printonly,
        no_touch_stds=True,
        timeout=None,
        check=True,
    )


################
# main
################

ARGS = None

# pylint: disable=duplicate-code
def main():
    """Main function - see -h for more info

    Note - this is a serial synchronous mock election loop.  A
    parallel loop would have one VTP server git workspace somewhere
    and N VTP scanner workspaces someplace else.  Depending on the
    network topology, it is also possible to start up VTP scanner
    workspaces on other machines as long as the git remotes and clones
    are properly configured (with access etc).

    While a mock election is running, it is also possible to use yet
    another VTP scanner workspace to personally cast/insert individual
    ballots for interactive purposes.

    Assumes that each supplied town already has the blank ballots
    generated and/or already committed.
    """

    # pylint: disable=global-statement
    global ARGS
    ARGS = parse_arguments()

    # Create an VTP election config object (this will perform an early
    # check on the ElectionData)
    the_election_config = ElectionConfig()
    the_election_config.parse_configs()

    # If an address was used, use that
    if ARGS.address or ARGS.state or ARGS.town or ARGS.substreet:
        the_address = Address.create_address_from_args(
            ARGS,
            [
                "blank_ballot",
                "device",
                "minimum_cast_cache",
                "flush_mode",
                "iterations",
                "verbosity",
                "printonly",
            ],
        )
        the_address.map_ggos(the_election_config)
        blank_ballot = the_election_config.gen_blank_ballot_location(
            the_address.active_ggos, the_address.ballot_subdir
        )
    elif ARGS.blank_ballot:
        blank_ballot = ARGS.blank_ballot

    # the VTP scanner mock simulation
    if ARGS.device in ["scanner", "both"]:
        scanner_mockup(the_election_config, blank_ballot)
    else:
        server_mockup(the_election_config)


if __name__ == "__main__":
    main()

# EOF