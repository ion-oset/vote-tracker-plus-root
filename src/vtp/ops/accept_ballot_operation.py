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
The logic of operation for accepting a ballot - the operation of
taking a filled in blank ballot and individually submitting each
contest level CVR in its own unique local git branch.  The git
branches are then pushed to the remote.  See merge-contest for the
operation of merging the pushed CVR branches to the main branch.
"""

# Standard imports
import logging
import os
import random
import secrets

# Project imports
from vtp.core.address import Address
from vtp.core.ballot import Ballot, Contests
from vtp.core.common import Globals, Shellout
from vtp.core.election_config import ElectionConfig
from vtp.ops.merge_contests_operation import MergeContestsOperation

# Local imports
from .operation import Operation


class AcceptBallotOperation(Operation):
    """Implementation of 'accept-ballot'."""

    def __init__(
        self,
        election_data_dir: str = "",
        guid: str = "",
        verbosity: int = 3,
        printonly: bool = False,
    ):
        """
        Primarily to module-ize the scripts and keep things simple,
        idiomatic, and in different namespaces.
        """
        super().__init__(election_data_dir, verbosity, printonly, guid)

    def get_random_branchpoint(self, branch):
        """Return a random branchpoint on the supplied branch

        Requires the CWD to be the parent of the CVRs directory.
        """
        result = Shellout.run(
            ["git", "log", branch, "--pretty=format:'%h'"],
            check=True,
            capture_output=True,
            text=True,
        )
        commits = [
            commit
            for commit in (line.strip("' ") for line in result.stdout.splitlines())
            if commit
        ]
        # the first record is never a real CVR
        # ZZZ why is the first record never a real CVR?
        #    del commits[-1]
        # ZZZ - need to deal with a rolling 100 window
        return random.choice(commits)

    def checkout_new_contest_branch(self, contest, ref_branch):
        """Will checkout a new branch for a specific contest.  Since there
        is no code yet to coordinate the potentially multiple scanners
        pushing to the same VC VTP git remote, use a highly unlikely GUID
        and try up to 3 times to get a unique branch.

        Requires the CWD to be the parent of the CVRs directory.
        """

        # select a branchpoint
        branchpoint = self.get_random_branchpoint(ref_branch)
        # and attempt at a new unique branch
        branch = (
            Globals.get("CONTEST_FILE_SUBDIR")
            + "/"
            + contest.get("uid")
            + "/"
            + secrets.token_hex(5)
        )
        #    branch = contest.get('uid') + "/" + str(uuid.uuid1().hex)[0:10]
        current_branch = Shellout.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        # if after 3 tries it still does not work, raise an error
        for _ in [0, 1, 2]:
            cmd1 = Shellout.run(
                ["git", "checkout", "-b", branch, branchpoint],
                printonly=self.printonly,
                verbosity=self.verbosity,
            )
            if cmd1.returncode == 0:
                # Created the local branch - see if it is push-able
                cmd2 = Shellout.run(
                    ["git", "push", "-u", "origin", branch],
                    printonly=self.printonly,
                    verbosity=self.verbosity,
                )
                if cmd2.returncode == 0:
                    # success
                    return branch
                # At this point there was some type of push failure - delete the
                # local branch and try again
                Shellout.run(
                    ["git", "checkout", current_branch],
                    check=True,
                    printonly=self.printonly,
                    verbosity=self.verbosity,
                )
                Shellout.run(
                    ["git", "branch", "-D", branch],
                    check=True,
                    printonly=self.printonly,
                    verbosity=self.verbosity,
                )
            # At this point the local did not get created - try again
            branch = contest.get("uid") + "/" + secrets.token_hex(5)

        # At this point the remote branch was never created and in theory the local
        # tries have also deleted(?)
        raise RuntimeError(f"could not create git branch {branch} on the third attempt")

    def get_unmerged_contests(self, config):
        """Queries git for the unmerged CVRs and returns the list.  See
        Shellout.cvr_parse_git_log_output for more info.  The returned
        list is still in git log order.
        """
        # Mmm, at the moment the thought is that we need all the unmerged
        # contests and ignore anything already merged.  So first get the
        # list of HEAD commits for all the unmerged branches.  Note that
        # since this is per contest, there should only be about 100 or so
        # of them.
        head_commits = (
            Shellout.run(
                [
                    "git",
                    "rev-list",
                    "--no-walk",
                    "--exclude=refs/heads/main",
                    "--exclude=HEAD",
                    "--exclude=refs/remotes/origin/main",
                    "--exclude=refs/remotes/origin/HEAD",
                    "--all",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .splitlines()
        )
        # With that list of HEAD exclusion commits, list the rest of the
        # --yes-walk commits and scrape that for the commits of interest.
        return Shellout.cvr_parse_git_log_output(
            ["git", "log", "--no-walk", "--pretty=format:%H%B"] + head_commits,
            config,
            verbosity=self.verbosity - 1,
        )

    def get_cloaked_contests(self, contest, branch):
        """Return a list of N cloaked cast CVRs for the specified contest.
        ZZZ - cloaking actually is a difficult problem because a cloaked
        value should only ever be given out once and regardless whatever
        value is given out can be cross checked with other ballot receipts.
        So a cloaked value is really only good if the digest is never
        really checked.

        Requires the CWD to be the parent of the CVRs directory.
        """
        this_uid = contest.get("uid")
        cloak_target = contest.get("cloak")
        return Shellout.run(
            [
                "git",
                "log",
                branch,
                "--oneline",
                "--all-match",
                '--grep={"CVR"}',
                f'--grep="uid": "{this_uid}"',
                f'--grep="cloak": "{cloak_target}"',
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def contest_add_and_commit(self, branch):
        """Will git add and commit the new contest content.
        Requires the CWD to be the parent of the CVRs directory.
        """
        # If this fails a shell error will be raised
        contest_file = os.path.join(
            Globals.get("CONTEST_FILE_SUBDIR"), Globals.get("CONTEST_FILE")
        )
        Shellout.run(
            ["git", "add", contest_file],
            printonly=self.printonly,
            verbosity=self.verbosity,
        )
        # Note - apparently git place the commit msg on STDERR - hide it
        Shellout.run(
            ["git", "commit", "-F", contest_file],
            printonly=self.printonly,
            verbosity=1,
        )
        # Capture the digest
        digest = Shellout.run(
            ["git", "log", branch, "-1", "--pretty=format:%H"],
            printonly=self.printonly,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return digest

    def create_ballot_receipt(
        self, the_ballot, contest_receipts, unmerged_cvrs, the_election_config
    ) -> tuple[list, int, str]:
        """
        Create the voter's receipt.  As of this writing this is basically
        a csv file with a header line with one row in particular being the
        voter's.
        """
        logging.debug("Ballot's digests:\n%s", contest_receipts)
        # Shuffled the unmerged_cvrs (an inplace shuffle) - only need to
        # shuffle the uids for this ballot.
        #    import pdb; pdb.set_trace()
        skip_receipt = False
        for uid in contest_receipts:
            # if there are no unmerged_cvrs, just warn
            if uid not in unmerged_cvrs:
                logging.warning("Warning - no unmerged_cvrs yet for contest %s", uid)
                skip_receipt = True
                continue
            if len(unmerged_cvrs[uid]) < Globals.get("BALLOT_RECEIPT_ROWS"):
                logging.warning(
                    "Warning - not enough unmerged CVRs (%s) to print receipt for contest %s",
                    len(unmerged_cvrs[uid]),
                    uid,
                )
                skip_receipt = True
            random.shuffle(unmerged_cvrs[uid])
        # Create the ballot receipt
        if skip_receipt:
            logging.warning("Skipping ballot receipt due to lack of unmerged CVRs")
            return [], 0, ""

        ballot_receipt = []
        #    import pdb; pdb.set_trace()
        # Not 0 based
        voters_row = random.randint(1, Globals.get("BALLOT_RECEIPT_ROWS"))
        # When there are not enough unmerged_receipts to print a receipt
        redacted_uids = set()
        # Add column headers - but include the long names as well
        next_row = []
        for uid in contest_receipts:
            next_row.append(
                '"'
                + uid
                + " - "
                + the_ballot.get_contest_name_by_uid(uid).replace('"', "'")
                + '"'
            )
        ballot_receipt.append(",".join(next_row))

        # Loop BALLOT_RECEIPT_ROWS times (the rows) filling in the ballots
        # uids as the columns.  Two notes: the range is the full
        # BALLOT_RECEIPT_ROWS because even though the voter's row is
        # inserted, the voter's digest might have ended up in the
        # unmerged_cvrs list.  When that happens, that digest needs to be
        # skipped and the voter's row digest from unmerged_cvrs used
        # instead.
        def inner_loop():
            for row in range(Globals.get("BALLOT_RECEIPT_ROWS")):
                if row == voters_row - 1:
                    # Include the voter's receipts instead
                    ballot_receipt.append(",".join(contest_receipts.values()))
                    continue
                next_row = []
                # Note - these are the voter's uids and digests
                for uid, digest in contest_receipts.items():
                    if uid not in unmerged_cvrs:
                        # Actually, there are _no_ other such cast uid's in
                        # this case
                        redacted_uids.add(uid)
                        next_row.append("INSUFFICIENT_CVRS")
                    elif row > len(unmerged_cvrs[uid]):
                        redacted_uids.add(uid)
                        next_row.append("INSUFFICIENT_CVRS")
                    elif digest == unmerged_cvrs[uid][row]["digest"]:
                        # This is the voter's own digest!
                        if voters_row - 1 > len(unmerged_cvrs[uid]):
                            redacted_uids.add(uid)
                            next_row.append("INSUFFICIENT_CVRS")
                        else:
                            next_row.append(
                                unmerged_cvrs[uid][voters_row - 1]["digest"]
                            )
                    else:
                        next_row.append(unmerged_cvrs[uid][row]["digest"])
                ballot_receipt.append(",".join(next_row))

        inner_loop()
        # Now need to redact any uid column that contains one or more
        # INSUFFICIENT_CVRS

        # Now write out the ballot_receipt in csv for now - can deal with
        # html (URL links) and a pdf (printable) later - both still a TBD.
        receipt_file = the_ballot.write_receipt_csv(ballot_receipt, the_election_config)
        # return all three
        return ballot_receipt, voters_row, receipt_file

    # pylint: disable=duplicate-code
    # pylint: disable=too-many-locals
    def run(
        self,
        an_address: Address = None,
        cast_ballot: str = "",
        cast_ballot_json: dict = "",
        merge_contests: bool = False,
    ) -> tuple[list, int]:
        """
        Main function - see -h for more info.  Will work with either
        specific or an generic address.

        Via the CLI nominally cast_ballot is specified as that is the
        only reasonable way to pass in a serialized or non-serialized
        JSON object.  However when called from within python,
        nominally cast_ballot_json is specified which is the python
        dict of the JSON.

        Incoming cast ballots are verified.
        """

        # Create a VTP ElectionData object if one does not already exist
        the_election_config = ElectionConfig.configure_election(self.election_data_dir)

        # Create a ballot
        a_ballot = Ballot()

        # Note - it probably makes the most sense to validate an
        # incoming_cast_ballot against the set of target blank_ballots
        # for the precinct (twon) so to catch the case of the wrong
        # cast_ballot being cast as well as malformed cast ballots.
        # However, that would imply that the ballot casting point
        # knows the specific address, which in reality is not the
        # case.  But, the precinct knows the range of legal addresses
        # - it knows which blank_ballots are legit.  So, the
        # verification can be against all the possible blank_ballots
        # of a precinct/town.

        # Note - accept_ballot.py currently only deals with generic
        # addresses since all cast ballots, regardless of active ggos, end
        # up in the same spot, nominally in the town subfolder.
        if cast_ballot:
            # Read the specified cast_ballot
            with Shellout.changed_cwd(the_election_config.get("git_rootdir")):
                a_ballot.read_a_cast_ballot("", the_election_config, cast_ballot)
        elif cast_ballot_json:
            a_ballot.set_ballot_data(cast_ballot_json)
        else:
            # The json was not supplied - in this case read the cast
            # ballot from the default location.
            an_address.map_ggos(the_election_config, skip_ggos=True)
            # Get the ballot for the specified address.  Note that reading
            # the cast ballot will define the active ggos etc for the
            # ballot even though those fields are not defined for the
            # address.  However, reading a ballot still needs the
            # ballot_subdir field of the address.
            a_ballot.read_a_cast_ballot(an_address, the_election_config)

        # Validate it
        a_ballot.verify_cast_ballot_data(the_election_config)

        # the voter's row of digests (indexed by contest uid)
        contest_receipts = {}
        # a cloaked receipt
        cloak_receipts = {}
        # 100 additional contest receipts
        unmerged_cvrs = {}

        # Set the three EV's
        os.environ["GIT_AUTHOR_DATE"] = "2022-01-01T12:00:00"
        os.environ["GIT_COMMITTER_DATE"] = "2022-01-01T12:00:00"
        os.environ["GIT_EDITOR"] = "true"

        # loop over contests
        branches = []
        contests = Contests(a_ballot)
        with Shellout.changed_cwd(a_ballot.get_cvr_parent_dir(the_election_config)):
            # So, the CWD in this block is the state/town subfolder

            # It turns out that determining the other not yet merged to
            # main contests is apparently a challangin git query and one
            # that creates a lot of temporary memory requirements.  One
            # current way to slice that pie is to just get all such
            # commits up front similar to the tally_contests.py code.
            # Then extract from that chunk of memory the contest with the
            # matching uid's of interest.  In the end this may be the
            # least expensive as the big reader is thus a stdout PIPE
            # loop.
            unmerged_cvrs = self.get_unmerged_contests(the_election_config)

            for contest in contests:
                #                import pdb; pdb.set_trace()
                with Shellout.changed_branch("main"):
                    # get N other values for each contest for this ballot
                    uid = contest.get("uid")
                    # atomically create the branch locally and remotely
                    branches.append(self.checkout_new_contest_branch(contest, "main"))
                    # Add the cast_branch to the contest json payload
                    contest.set("cast_branch", branches[-1])

                    # They is an interest to add a contest runtime digest
                    # key value pair which is a cryptographic value
                    # derived from the run-time election private key. This
                    # value could also read via read_contest and can be
                    # validated against the election public key if
                    # available. However, the 'lack of appearance of
                    # trustworthiness' in that a 'cryptic' number is being
                    # written/associated with the contest cvr that by
                    # definition would contain something obaque is not an
                    # effective improvement. So, do not so this. Leave the
                    # insertion of a runtime digest at merge time, which
                    # occurs later and independent of contest commit time
                    # and any potential voter information.

                    # Write out the voter's contest to CVRs/contest.json
                    a_ballot.write_contest(contest, the_election_config)
                    # commit the voter's contest
                    contest_receipts[uid] = self.contest_add_and_commit(branches[-1])
                    # if cloaking, get those as well
                    if "cloak" in contest.get("contest"):
                        cloak_receipts[uid] = self.get_cloaked_contests(contest, "main")
            # After all the contests digests have been generated as well
            # as the others and cloaks as much as possible, then push as
            # atomically as possible all the contests.
            for branch in branches:
                Shellout.run(
                    ["git", "push", "origin", branch],
                    printonly=self.printonly,
                    verbosity=self.verbosity,
                )
                # Delete the local as they build up too much.  The local
                # reflog keeps track of the local branches
                Shellout.run(
                    ["git", "branch", "-d", branch],
                    printonly=self.printonly,
                    verbosity=self.verbosity,
                )

        # If in demo mode, optionally merge the branches now and avoid
        # calling merge-contests later. Note - this will serialize the
        # ballots in time, but this is ok in certain demo situations.
        # Note - since the above git push/delete is trying to be
        # automic, at the moment that is done in the above loop and
        # then later (now) the merge into main is done.  Since the
        # above deletes the local CVR branch reference, the
        # merge-contests below needs to merge directly from the remote
        # reference.  (One could also do the merge prior to the local
        # branch reference deletion and let the merge operation itself
        # delete both branch references.)
        if merge_contests:
            for branch in branches:
                # Merge the branch (but since the local branch should be
                # deleted at this point, merge the remote).  Note -
                # 'origin' is already hardcoded in several places and
                # 'remotes' is enough of a constant for this.
                mco = MergeContestsOperation(
                    election_data_dir=self.election_data_dir,
                    verbosity=self.verbosity,
                    printonly=self.printonly,
                )
                logging.debug("Calling MergeContestsOperation.run")
                mco.run(
                    branch="origin/" + branch,
                    flush=False,
                    remote=True,
                )

        # Create the ballot check
        ballot_check, index, receipt_file = self.create_ballot_receipt(
            a_ballot, contest_receipts, unmerged_cvrs, the_election_config
        )

        # For now, print the location and the voter's index
        print(f"############\n### Receipt file: {receipt_file}")
        print(f"### Voter's row: {index}\n############")
        # And return two
        return ballot_check, index


# EOF
