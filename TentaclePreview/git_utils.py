from typing import List, Literal

from github.Branch import Branch
from github.Repository import Repository


def get_filtered_github_repo_branches(repo: Repository,
                                      filter_mode: Literal["exclude", "include"] = "exclude",
                                      filter_branches: List[str] | None = None) -> List[Branch]:
    if filter_branches:
        match filter_mode:
            case "exclude":
                branch_filter = lambda branch: branch.name not in filter_branches
            case "include":
                branch_filter = lambda branch: branch.name in filter_branches
            case _:
                raise ValueError(f"Invalid filter mode: {filter_mode}")

    branches = list(repo.get_branches())

    # TODO maybe storage branch names only
    # branches = [branch.name for branch in branches]
    if filter_branches:
        branches = list(filter(branch_filter, branches))

    return branches
