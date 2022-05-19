#!/usr/bin/python3.6
import re
import subprocess
import sys

from pick import pick

def branch_pattern(branch_name='.+?'):
    return re.compile(r'\|-> (?P<raw_branch_name>{branch_name}) '.format(branch_name=branch_name))


def extract_raw_branch_name(line, pattern=branch_pattern()):
    m = pattern.search(line)
    if not m:
        return None
    return m.group('raw_branch_name')


def main(argv=sys.argv[1:]):
    # Make sure we filter empty string.
    gf_status = [line for line in subprocess.check_output('gitflow --no-color'.split()).decode('utf-8').split('\n') if line]

    # Create a lookup from the gitflow status output to raw branch name.
    # This will allow us to select a line from the gitflow status and map it to a branch to delete.
    gf_to_raw_branch_map = {}
    gf_status_options = []
    for line in gf_status:
        raw_branch_name = extract_raw_branch_name(line)
        if raw_branch_name is None:
            continue
        gf_to_raw_branch_map[line] = raw_branch_name

    selections = pick(options=gf_status,
                  title=("Mark all branches you would like to delete.\n"
                         "Navigate with arrow keys.\n"
                         "Select multiple with [space]."),
                  multiselect=True,
                  indicator='->')
    for line, _ in selections:
      # Hardcode that we skip the remote branches if they are selected.
      if re.match(r'\s*origin\/', line):
        continue
      # Check if able to prune. Log failure.
      if line not in gf_to_raw_branch_map:
        print(f"Warning! Could not find raw branch name for {line}")
        continue
      raw_branch_name = gf_to_raw_branch_map[line]
      # Delete the branch.
      subprocess.check_call(f'git branch -D {raw_branch_name}', shell=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
