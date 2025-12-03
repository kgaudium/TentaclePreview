import json
import os
import shutil
from typing import Any, Dict

from github import Github

from TentaclePreview import output
from TentaclePreview.git_utils import *
from TentaclePreview.tentacle import Tentacle

TENTACLES_LIST: List[Tentacle] = []
SYSTEM_LOGS: List[output.LogEntry] = []
CONFIG: Dict[str, Any] = {}
GITHUB_INSTANCE: Github | None = None
REPO: Repository | None = None

def add_system_log(log_entry: output.LogEntry, **kwargs: dict[str, Any]) -> None:
    global SYSTEM_LOGS
    SYSTEM_LOGS.append(log_entry)

def system_logs_to_json() -> list[Any]:
    global SYSTEM_LOGS
    return list(map(lambda log: log.__json__(), SYSTEM_LOGS))

output.on_log_event.append(add_system_log)

def get_tenty_by_name(name: str) -> Tentacle | None:
    global TENTACLES_LIST
    return next((t for t in TENTACLES_LIST if t.name == name), None)


def init_globals(config_path: str) -> None:
    global CONFIG, GITHUB_INSTANCE, REPO
    # TODO add try catches
    # TODO add custom_commands: Dict["branch_name", "cmd_dict"]
    CONFIG = json.load(open(config_path))

    output.log(f"Configuration loaded from {config_path}", "success")

    output.ENABLED_LOG_LEVELS = CONFIG["enabled_log_levels"]
    GITHUB_INSTANCE = Github(CONFIG["github_token"])
    REPO = GITHUB_INSTANCE.get_repo(CONFIG["repo_full_name"])

    output.log(f"Watching repository {CONFIG['repo_full_name']}", "success")


def delete_tentacle(name: str) -> None:
    global TENTACLES_LIST

    tenty = get_tenty_by_name(name)
    if tenty:
        TENTACLES_LIST.remove(tenty)
        tenty.clear_files()


def clear_redundant_local_branches(remote_branches: List[Branch]) -> None:
    global CONFIG

    output.log(f"Clearing redundant local branches", "info")

    branches_dir = CONFIG["branches_dir"]
    if not os.path.exists(branches_dir):
        return

    local_branches = [
        name for name in os.listdir(branches_dir)
        if os.path.isdir(os.path.join(branches_dir, name))
    ]

    remote_branches_names = [br.name for br in remote_branches]

    for branch in local_branches:
        if branch not in remote_branches_names:
            branch_path = os.path.join(branches_dir, branch)
            try:
                shutil.rmtree(branch_path)
                output.log(f"Local branch {branch} deleted", "success")
            except Exception as e:
                output.log(f"Error occurred while deleting local branch {branch}: {e}", "error")


def init_tentacles() -> None:
    global TENTACLES_LIST, CONFIG, REPO, GITHUB_INSTANCE

    branches = get_filtered_github_repo_branches(REPO, CONFIG["filter_mode"], CONFIG["filter_branches"])

    if CONFIG.get("clear_redundant_local_branches", True):
        clear_redundant_local_branches(branches)

    output.log(f"Watching {len(branches)} branches", "success")

    for branch in branches:
        new_branch_server = Tentacle(remote_repo=REPO, remote_branch=branch, branches_dir=CONFIG["branches_dir"],
                                     commands=CONFIG["commands"])
        TENTACLES_LIST.append(new_branch_server)


def start_tentacles() -> None:
    global TENTACLES_LIST

    for tenty in TENTACLES_LIST:
        tenty.build()
        tenty.start()

    for tenty in TENTACLES_LIST:
        output.log(str(tenty), "header")


def stop_tentacles() -> None:
    global TENTACLES_LIST

    for tenty in TENTACLES_LIST:
        tenty.stop()


def proceed_webhook_event(json_data) -> None:
    global TENTACLES_LIST, CONFIG, REPO, GITHUB_INSTANCE

    if not CONFIG["webhook_update"]:
        output.log(f"Got webhook, but webhook update is disabled in config", "warning")
        return

    output.log(f"Received event from: {json_data.get('repository', {}).get('full_name')}", "header")
    output.log(f"Triggered by: {json_data.get('sender', {}).get('login')}")

    branch_name = json_data["ref"].split("/")[-1]

    tenty = get_tenty_by_name(branch_name)
    if tenty is not None:
        if json_data["after"] == "0000000000000000000000000000000000000000":
            get_tenty_by_name(branch_name).stop()
            delete_tentacle(branch_name)
            return

        tenty.update()
        return

    new_tenty = Tentacle(remote_repo=REPO, remote_branch=branch_name, branches_dir=CONFIG["branches_dir"],
                         commands=CONFIG["commands"])
    TENTACLES_LIST.append(new_tenty)
    new_tenty.build()
    new_tenty.start()


def init_webhook() -> None:
    raise NotImplementedError  # add webhook to GITHUB_INSTANCE


def init():
    output.log("Git Init Stage", "header")
    init_tentacles()

    output.log(f"Tentacles Init Stage", "header")
    start_tentacles()
