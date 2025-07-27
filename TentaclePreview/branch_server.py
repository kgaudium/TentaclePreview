from pathlib import Path
from typing import Dict, List

from git import Repo
from github.Branch import Branch
from github.Repository import Repository

from TentaclePreview.output import log, progress


# TODO rename to Tentacle (or cutie version of Tentacle)
class Tentacle:
    def __init__(self, remote_repo: Repository, remote_branch: Branch | str, branches_dir: Path,
                 commands: Dict[str, str | List[str]]):
        if type(remote_repo) != Repository:
            raise TypeError("remote_repo must be of type Repository")

        self._remote_repo: Repository = remote_repo

        self.remote_branch: Branch | str = None
        if type(remote_branch) == Branch:
            self.remote_branch = remote_branch
        elif type(remote_branch) == str:
            self.remote_branch = self._remote_repo.get_branch(remote_branch)
        else:
            raise TypeError("Branch must be of type Branch or str")

        self._path: Path = branches_dir / Path(self.name)
        self._commands: Dict[str,  str | List[str]] = commands
        if not {"start", "build"}.issubset(self._commands):
            raise ValueError("'start' and 'build' commands must exist")

        self._local_repo: Repo | None = None
        self._port: int | None = None
        self.is_build_success: bool | None = None
        self.is_start_success: bool | None = None
        self.build_error: str | None = None
        self.start_error: str | None = None

        if self.path.exists():
            log(f"Branch '{self.remote_branch.name}' folder already exists. Loading...")
            try:
                self.local_repo = Repo(self.path)
            except Exception as e:
                log(f"Cannot load '{self.remote_branch.name}' branch!\n{e}", 'error')
            log(f"Branch '{self.remote_branch.name}' loaded!", 'success')
        else:
            log(f"Cloning branch '{self.remote_branch.name}'...")
            self.local_repo = Repo.clone_from(self.repo_url, self.path, branch=self.name, depth=1, progress=progress)
            log(f"Branch '{self.remote_branch.name}' cloned!", 'success')

    def start(self):
        log(f"Starting tentacle '{self.remote_branch.name}'...")
        pass

    def stop(self):
        log(f"Stoping tentacle '{self.remote_branch.name}'...")
        pass

    def build(self):
        log(f"Building tentacle '{self.remote_branch.name}'...")
        pass

    # TODO "clean" arg - clears branch folder and clone it again
    def update(self):
        self.stop()

        log(f"Updating tentacle '{self.remote_branch.name}'...")
        self.local_repo.git.fetch("--all", "--force", "--prune", progress=progress)
        log(f"Tentacle '{self.remote_branch.name}' fetched!", 'success')

        self.build()
        self.start()

    @property
    def local_repo(self) -> Repo:
        return self._local_repo

    @local_repo.setter
    def local_repo(self, value: Repo) -> None:
        self._local_repo = value
        self._local_repo.git.checkout(self.name, force=True)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def repo_url(self) -> str | None:
        if self._remote_repo is None:
            return None

        result = self._remote_repo.clone_url
        if self._remote_repo.requester.auth:
            result = result.replace("https://", f"https://{self._remote_repo.requester.auth.token}@")

        return result

    @property
    def update_required(self) -> bool:
        if self.local_repo is None:
            return True

        return self.remote_branch.commit.sha != self.local_repo.head.commit.sha

    @property
    def name(self) -> str:
        return self.remote_branch.name

    # TODO: проверка доступности порта
    @property
    def port(self) -> int | None:
        return self._port

    @port.setter
    def port(self, value: int) -> None:
        self._port = value

    def __str__(self) -> str:
        status = "OFF"
        if self.is_build_success:
            status = "BUILT"

        if self.is_start_success:
            status = "STARTED"

        return f"BranchServer({self.name}, on port:{self.port}, {status})"

    def __repr__(self) -> str:
        return self.__str__()
