import json
from typing import Any, Dict

from github import Github

from TentaclePreview.branch_server import Tentacle
from TentaclePreview.git_utils import *
from TentaclePreview import output

TENTACLES_LIST: List[Tentacle] = []
CONFIG: Dict[str, Any] = {}
GITHUB_INSTANCE: Github | None = None
REPO: Repository | None = None


def init_globals(config_path: str) -> None:
    global CONFIG, GITHUB_INSTANCE, REPO
    # TODO add try catches
    CONFIG = json.load(open(config_path))

    output.log(f"Configuration loaded from {config_path}", "success")

    output.ENABLED_LOG_LEVELS = CONFIG["enables_log_levels"]
    GITHUB_INSTANCE = Github(CONFIG["github_token"])
    REPO = GITHUB_INSTANCE.get_repo(CONFIG["repo_full_name"])

    output.log(f"Watching repository {CONFIG['repo_full_name']}", "success")


def init_tentacles() -> None:
    global TENTACLES_LIST, CONFIG, REPO, GITHUB_INSTANCE

    branches = get_filtered_github_repo_branches(REPO, CONFIG["filter_mode"], CONFIG["filter_branches"])
    # TODO найти какое-нибудь слово по типу обвиваю ну типа щупальцы да
    output.log(f"Watching {len(branches)} branches", "success")

    for branch in branches:
        new_branch_server = Tentacle(remote_repo=REPO, remote_branch=branch, branches_dir=CONFIG["branches_dir"],
                                     commands=CONFIG["commands"])
        TENTACLES_LIST.append(new_branch_server)


def start_tentacles() -> None:
    pass


def init_webhook() -> None:
    raise NotImplementedError # add webhook to GITHUB_INSTANCE


def init(config_path: str = "./config.json"):
    output.log(f"Initializing Tentacle Preview...", "header")
    init_globals(config_path)
    output.log("Git Init Stage", "header")
    init_tentacles()

    output.log(f"Tentacles Init Stage", "header")
    output.log("Only init implemented yet", "error")
