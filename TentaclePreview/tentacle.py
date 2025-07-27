import os
import platform
import shlex
import signal
from pathlib import Path
import subprocess
import socket
from typing import Dict, List

from git import Repo
from github.Branch import Branch
from github.Repository import Repository

from TentaclePreview.output import log, progress


class Tentacle:
    def __init__(self, remote_repo: Repository, remote_branch: Branch | str, branches_dir: Path,
                 commands: Dict[str, str | List[str]]):
        if type(remote_repo) != Repository:
            raise TypeError("remote_repo must be of type Repository")

        self._remote_repo: Repository = remote_repo

        if isinstance(remote_branch, Branch):
            self.remote_branch = remote_branch
        elif isinstance(remote_branch, str):
            self.remote_branch = self._remote_repo.get_branch(remote_branch)
        else:
            raise TypeError("remote_branch must be of type Branch or str")

        self._path: Path = branches_dir / Path(self.name)
        self._commands: Dict[str, str | List[str]] = commands
        if not {"start", "build"}.issubset(self._commands):
            raise ValueError("'start' and 'build' commands must exist")

        self._local_repo: Repo | None = None
        self._process: subprocess.Popen | None = None
        self._host: str = "127.0.0.1"
        self._port: int = self._find_free_port()

        self.is_build_success: bool | None = None
        self.is_start_success: bool | None = None
        self.build_error: str | None = None
        self.start_error: str | None = None

        if self.path.exists():
            self._load_repo_from_path()
        else:
            self._clone_repo_from_remote()


    def _load_repo_from_path(self):
        log(f"Found existing folder for branch '{self.name}'. Attempting to load...")
        try:
            self.local_repo = Repo(self.path)
            log(f"Successfully loaded branch '{self.name}'.", "success")
        except Exception as e:
            log(f"Failed to load local repository for branch '{self.name}': {e}", "error")
            raise

    def _clone_repo_from_remote(self):
        log(f"Cloning branch '{self.name}' from remote...")
        try:
            self.local_repo = Repo.clone_from(
                self.repo_url,
                self.path,
                branch=self.name,
                depth=1,
                progress=progress
            )
            log(f"Successfully cloned branch '{self.name}'.", "success")
        except Exception as e:
            log(f"Failed to clone branch '{self.name}': {e}", "error")
            raise

    # TODO "clean" arg - clears branch folder and clone it again
    def update(self):
        self.stop()

        log(f"Updating tentacle '{self.name}'...")
        self.local_repo.git.fetch("--all", "--force", "--prune", progress=progress)
        log(f"Tentacle '{self.name}' fetched!", "success")

        self.build()
        self.start()

    def _render_command(self, command: str) -> str:
        try:
            return command.format(**self._command_context)
        except KeyError as e:
            log(f"Missing context variable in command: {e}", "error")
            raise

    def build(self):
        log(f"Building tentacle '{self.name}'...")

        commands = self._commands.get("build", [])
        if isinstance(commands, str):
            commands = [commands]

        self.is_build_success = True
        self.build_error = None

        for raw_cmd in commands:
            if not raw_cmd.strip():
                continue

            cmd = self._render_command(raw_cmd)
            log(f"Running build step: '{cmd}'", status="info")

            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(self.path),
                    shell=True,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if result.stdout:
                    log(f"'{cmd}' output:\n{result.stdout.strip()}", "info")
                if result.stderr:
                    log(f"'{cmd}' errors:\n{result.stderr.strip()}", "warning")
            except subprocess.CalledProcessError as e:
                self.is_build_success = False
                self.build_error = e.stderr
                log(f"Build step failed:\n{e.stderr}", "error")
                break

        if self.is_build_success:
            log(f"Tentacle '{self.name}' built successfully.", "success")

    def start(self):
        log(f"Starting tentacle '{self.name}'...")

        if self._process and self._process.poll() is None:
            log(f"Tentacle '{self.name}' is already running.", status="warning")
            return

        cmd = self._commands.get("start")
        if not cmd:
            log("No start command provided.", status="error")
            return

        # Подготовка окружения для замены плейсхолдеров
        context = {
            "path": str(self.path),
            "host": "127.0.0.1",
            "port": str(self.port or 0),
        }
        if isinstance(cmd, str):
            cmd = cmd.format(**context)

        is_windows = platform.system() == "Windows"

        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0,
                preexec_fn=os.setsid if not is_windows else None
            )
            self.is_start_success = True
            self.start_error = None
            log(f"Tentacle '{self.name}' started.", status="success")
        except Exception as e:
            self.is_start_success = False
            self.start_error = str(e)
            log(f"Failed to start tentacle:\n{e}", status="error")

    def stop(self):
        log(f"Stopping tentacle '{self.name}'...", status="header")

        if self._process and self._process.poll() is None:
            try:
                is_windows = platform.system() == "Windows"

                if is_windows:
                    self._process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    pgid = os.getpgid(self._process.pid)
                    os.killpg(pgid, signal.SIGTERM)

                self._process.wait(timeout=5)
                log(f"Tentacle '{self.name}' stopped.", "success")
            except subprocess.TimeoutExpired:
                log("Process did not exit gracefully, killing...", "warning")
                self._process.kill()
                log(f"Tentacle '{self.name}' killed.", "success")
            except Exception as e:
                log(f"Error while stopping tentacle: {e}", "error")
        else:
            log("No running process to stop.", "info")

        self._process = None

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

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

    # TODO: проверка доступности порта на сеттер
    @property
    def port(self) -> int | None:
        return self._port

    @port.setter
    def port(self, value: int) -> None:
        self._port = value

    @property
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        self._host = value

    @property
    def _command_context(self) -> Dict[str, str | int]:
        return {
            "host": self._host,
            "port": self._port,
            "path": str(self.path),
            "branch": self.name
        }

    def __str__(self) -> str:
        status = "OFF"
        if self.is_build_success:
            status = "BUILT"

        if self.is_start_success:
            status = "STARTED"

        return f"BranchServer({self.name}, on port:{self.port}, {status})"

    def __repr__(self) -> str:
        return self.__str__()
