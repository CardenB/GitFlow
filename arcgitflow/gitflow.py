#!/usr/bin/python3.6
"""
TODOs:
    * If you have a root branch, instead of pointing them toward origin,
      tag them as remote and print divergence from origin.
"""
# System imports
import argparse
import os
import sys
from collections import defaultdict

# Third-party imports
import git
from six import string_types
from termcolor import colored


class DagParseException(Exception):
    pass


class CascadeException(Exception):
    pass


def branch_name(branch):
    """
    Get the name of a branch object. Deals with a branch as a string.

    :input branch: GitPython Branch object. Can also be a string.

    :return: String name of the branch.
    """
    assert branch is not None, "Must have a valid branch to get the name!"
    if isinstance(branch, string_types):
        return branch
    name = branch.name.lstrip("./")
    return name


def commit_delta_by_branch_name(cur_branch_name, parent_branch_name, repo):
    cmd = [
        "git",
        "rev-list",
        "--count",
        "--left-right",
        "{}...{}".format(cur_branch_name, parent_branch_name),
    ]
    try:
        delta_str = repo.git.execute(cmd)
        parent_divergence, cur_branch_divergence = [
            int(count.strip()) for count in delta_str.split()
        ]
        return parent_divergence, cur_branch_divergence
    except Exception:
        return None, None


def commit_delta_by_branch(cur_branch, repo):
    cur_branch_name = branch_name(cur_branch)
    parent_branch_name = branch_name(cur_branch.tracking_branch())
    return commit_delta_by_branch_name(cur_branch_name, parent_branch_name, repo)


def replace_colored(string, *args, **kwargs):
    return string


def create_branch_str(bname, active_branch, depth, parent_bname="", repo=None, no_color=False):
    color_fn = colored
    if no_color:
        color_fn = replace_colored
    # Create a string with whitespace representing depth.
    tabstr = "".join(["  "] * depth)
    if depth == 0:
        branch_str = " {branch}".format(tabstr, branch=bname)
    else:
        branch_str = "{} |-> {branch}".format(tabstr, branch=bname)

    # If given enough information, print the status relative to the parent.
    if parent_bname and repo:
        (cur_ahead, parent_ahead) = commit_delta_by_branch_name(bname, parent_bname, repo)
        branch_str += "  "
        if parent_ahead:
            parent_ahead_str = color_fn("-{}".format(str(parent_ahead)), "red")
        elif parent_ahead == 0:
            parent_ahead_str = "-{}".format(str(parent_ahead))
        else:
            parent_ahead_str = "?"
        if cur_ahead:
            cur_ahead_str = color_fn("+{}".format(str(cur_ahead)), "green")
        elif cur_ahead == 0:
            cur_ahead_str = "-{}".format(str(cur_ahead))
        else:
            cur_ahead_str = "?"

        if cur_ahead is None or parent_ahead is None:
            branch_str += "(Upstream Branch Not Found)"
            branch_str = color_fn(branch_str, "red")
        else:
            branch_str += "({}, {})".format(parent_ahead_str, cur_ahead_str)

    # Highlight the current branch in terminal if it is currently checked
    # out.
    active_bname = branch_name(active_branch)
    if active_bname is not None and bname == active_bname:
        branch_str += " *(active branch)"
        branch_str = color_fn(branch_str, "green")
    return branch_str


def active_branch_from_repo(repo, verbose=False):
    if repo is None:
        return None
    try:
        return repo.active_branch
    except TypeError as e:
        if verbose:
            print("Could not get active branch due to error: {}".format(str(e)))
        return None


def refresh_branch(branch, repo):
    try:
        repo.remote().fetch(branch_name(branch))
        cmd = ["git", "reset", "--keep", "origin/{}".format(branch_name(branch))]
        repo.git.execute(cmd)
    except Exception as e:
        print(
            "Failed to refresh {} with error:\n{}".format(
                branch_name(branch), colored(str(e), "red")
            )
        )


def get_merge_base(repo: git.Repo, branch1: str, branch2: str) -> str:
    """
    Get the merge base commit for two branches.
    """
    ancestor_list = repo.merge_base(branch1, branch2)
    if not ancestor_list:
        raise Exception("No ancestor found between {} and {}".format(branch1, branch2))
    return ancestor_list[0]


def abort_reabse(repo: git.Repo) -> None:
    """
    Aborts a rebase in progress.
    Applies exception handling so the process doesn't crash if no rebase is in progress.

    :input repo: GitPython repo object handle for dealing with git metadata.
    """
    try:
        repo.git.rebase(abort=True)
    except git.GitCommandError as e:
        print(colored("Skipping abort rebase since no rebase is in progress", "red"))
        print(colored(str(e), "yellow"))


def force_push_no_verify(repo: git.Repo, branch: str) -> None:
    """
    Force push to origin without verification.
    Uses exception handling to abort the push without interrupting anything else.

    :input repo: GitPython repo object handle for dealing with git metadata.
    :input branch: String name of the branch to push.
    """
    try:
        print(f"git push --force origin {branch} --no-verify")
        repo.git.push("--force", "origin", branch, "--no-verify")
    except git.GitCommandError as e:
        print(colored("Failed to push branch due to error:", "red"))
        print(colored(str(e), "yellow"))
        print(
            colored(
                "Aborting cascade for this branch. "
                "Please resolve conflicts on your own.",
                "red",
            )
        )

def rebase_onto(repo: git.Repo, new_base: str, feature_branch: str) -> str:
    """
    Efficiently rebase feature branch onto new base branch.
    """
    rebase_cmd_str = f"git rebase -i --reapply-cherry-picks --fork-point {new_base} {feature_branch}"
    print(rebase_cmd_str)
    repo.git.rebase(
            "--reapply-cherry-picks", "--fork-point", new_base, feature_branch # , "--rebase-merges"  # TODO(carden): Investigate pros/cons of rebase-merges.
    )
    return rebase_cmd_str


def get_commit_for_branch(branch):
    # print(f"Getting commit for branch: {branch}")
    commit = branch.commit
    # Deal with the case where merges are present.
    while len(commit.parents) > 1:
        commit = commit.parents[0]  # Follow the first parent
    # print(f"Commit for branch {branch} is: {commit}")
    return commit


def print_tree(
    dag,
    current_branch_name,
    depth,
    repo: git.Repo,
    cascade=False,
    color=True,
    push_updates=False,
):
    """
    Prints the git flow dependency tree recursively.
    Ex:
     master
       |-> my_feature_branch_0
         |-> my_current_feature_branch *
    Will terminate when a branch that is not in the dag is found or when there
    are no remaining child branches for teh current branch.

    :input dag: The gitflow graph that tracks dependencies.
    :input current_branch_name: String name of the branch for the current
                                recursive call.
    :input depth: Integer indicating the depth of the current tree.
    :input repo: GitPython repo object handle for dealing with git metadata.
    :input cascade: Boolean that, when True, will cause cascaded rebases to
                    occur, rebasing each child branch onto the parent branch
                    via `git pull --rebase [parent_branch]`.
                    Defaults to False.
    """
    # Print the active branch differently
    active_branch = active_branch_from_repo(repo)
    # Do not print branch if it is not in the flow dag.
    if current_branch_name not in dag:
        return True
    if depth == 0:
        print(create_branch_str(current_branch_name, active_branch, depth, no_color=not color))
        return print_tree(
            dag,
            current_branch_name,
            depth + 1,
            repo,
            cascade=cascade,
            color=color,
            push_updates=push_updates,
        )
    # Recurively print branches in the flow dag.
    for branch in dag[current_branch_name]:
        # print(f"dag for current branch: {current_branch_name}")
        # print(dag[current_branch_name])
        bname = branch_name(branch)
        # Print the final branch string to terminal.
        print(
            create_branch_str(
                bname,
                active_branch,
                depth,
                branch_name(branch.tracking_branch()),
                repo,
                no_color=not color,
            )
        )

        # Perform the cascaded rebase if specified.
        if cascade:
            if repo is None:
                raise CascadeException("Must also supply a repo!")
            print(
                "Rebasing {cur_branch} onto {parent_branch}...".format(
                    cur_branch=bname, parent_branch=branch_name(branch.tracking_branch())
                )
            )
            try:
                rebase_cmd_str = rebase_onto(
                    repo,
                    new_base=branch_name(branch.tracking_branch()),
                    feature_branch=bname,
                )
                print(f"Rebase command: {rebase_cmd_str}")
                if push_updates:
                    force_push_no_verify(repo, bname)
            except git.GitCommandError as e:
                print(colored("Failed cascade due to error:", "red"))
                print(colored(str(e), "yellow"))
                print(
                    colored(
                        "Aborting cascade for this branch. "
                        "Please resolve conflicts on your own.",
                        "red",
                    )
                )
                print("Continuing to next subtree...")
                abort_reabse(repo)
                continue
        leaf_node_reached = print_tree(
            dag,
            bname,
            depth + 1,
            repo,
            cascade=cascade,
            color=color,
            push_updates=push_updates,
        )
        if not leaf_node_reached:
            return False
    return True


def build_git_dag(r):
    """
    Build the gitflow branch dependency graph.

    :input repo: The GitPython repository handle.

    :return: A dict of key, branch name, to list, GitPython branch objects.
    """
    # Key branch name to list of child branches.
    dag = defaultdict(list)
    roots = []
    for b in r.branches:
        bname = branch_name(b)
        dag.setdefault(bname, [])
        tb = b.tracking_branch()
        if tb:
            tbname = branch_name(tb)
            if tbname.startswith("origin"):
                roots.append(tbname)
            dag[tbname].append(b)
        else:
            roots.append(bname)
    return dag, roots


def print_dag(
    dag: dict,
    roots: list,
    repo: git.Repo,
    cascade: bool,
    color: bool = True,
    push_updates: bool = False,
):
    # Begin traversing the tree from the top level branches.
    for root_branch_name in roots:
        if not print_tree(
            dag,
            root_branch_name,
            depth=0,
            repo=repo,
            cascade=cascade,
            color=color,
            push_updates=push_updates,
        ):
            return


def checkout(branch_name, repo, fail=True):
    """
    Checkout a branch with some exception handling to check for branch
    existance.

    :input fail: If True, will raise an exception on failure. Otherwise will
                 return a boolean to determine checkout success.

    :return: Boolean to indicate checkout success.
    """
    try:
        repo.git.checkout(branch_name)
    except repo.exc.GitCommandError as e:
        print("Branch, {}, likely does not exist".format(branch_name))
        if fail:
            raise e
        return False
    return True


def find_git_dir():
    """
    Finds the git directory no matter where your current working directory is.
    """
    # Use `--show-toplevel` instead of `--git-dir` here because it is a more
    # robust solution.
    cmd = ["git", "rev-parse", "--show-toplevel"]
    g = git.Git()
    # We join with .git instead of doing `--git-dir` in our cmd because this
    # works with worktrees, while `--git-dir` did not work with worktrees in my
    # experience. Worst case, both work.
    return os.path.join(g.execute(cmd), ".git")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cascade",
        default=False,
        action="store_true",
        help="When specified, will rebase all downstream branches from this " "branch.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="When specified, will print the git dag starting from this "
        "branch. Will also cascade from this branch only when specified."
        "Defaults to currently checked out branch.",
    )
    parser.add_argument(
        "--refresh",
        default=False,
        action="store_true",
        help="Updates the specified branch with latest origin.",
    )
    parser.add_argument(
        "--no-color",
        default=True,
        dest="color",
        action="store_false",
        help="Updates the specified branch with latest origin.",
    )
    parser.add_argument(
        "--push",
        default=False,
        action="store_true",
        help="Pushes changes to origin after rebasing. Will use --force-with-lease. Should typically be used with --cascade.",
    )
    return parser.parse_args(argv)


def main(argv=sys.argv[1:]):
    args = parse_args(argv)
    git_dir = find_git_dir()
    if not (os.path.exists(git_dir)):
        raise DagParseException("Must be in git directory!")
    repo = git.Repo(os.path.dirname(git_dir))
    dag, roots = build_git_dag(repo)

    # By default, start with the currently checked out branch.
    initial_active_branch = active_branch_from_repo(repo, verbose=True)
    active_branch_name = None
    if initial_active_branch:
        active_branch_name = branch_name(initial_active_branch)

    if not args.branch:
        args.branch = active_branch_name
    else:
        # Branch names to start dags from.
        roots = [args.branch]
    if args.branch != active_branch_name:
        active_branch_name = args.branch
        checkout(active_branch_name, repo)

    if args.refresh:
        refresh_branch(active_branch_name, repo)

    if args.cascade:
        roots = [active_branch_name]
    print_dag(dag, roots, repo, args.cascade, color=args.color, push_updates=args.push)
    # If performing a cascade, print out status again.
    if args.cascade:
        # If cascaded, return to the original branch.
        repo.git.checkout(initial_active_branch)

        print("Status after cascade:")
        print_dag(dag, roots, repo, False, color=args.color, push_updates=False)


if __name__ == "__main__":
    sys.exit(main())
