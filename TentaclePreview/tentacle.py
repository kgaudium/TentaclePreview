import os
import platform
import shutil
import signal
import socket
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Literal, Optional

from git import Repo
from github.Branch import Branch
from github.Repository import Repository

from TentaclePreview.output import log, progress


class Tentacle:
    _broadcast_status = None  # callable(name, build_status, start_status)
    _broadcast_logs = None  # callable(name, log_type, logs_dict, stream=False)

    @classmethod
    def set_broadcast_callbacks(cls, logs_callback, status_callback):
        cls._broadcast_logs = logs_callback
        cls._broadcast_status = status_callback

    def __init__(self, remote_repo: Repository, remote_branch: Branch | str, branches_dir: Path,
                 commands: Dict[str, str | List[str]]):
        if not isinstance(remote_repo, Repository):
            raise TypeError("remote_repo must be of type Repository")

        self._remote_repo = remote_repo
        self.remote_branch = (
            remote_branch if isinstance(remote_branch, Branch)
            else self._remote_repo.get_branch(remote_branch)
        )

        self._path: Path = branches_dir / Path(self.name)
        self._commands: Dict[str, str | List[str]] = commands
        if not {"start", "build"}.issubset(self._commands):
            raise ValueError("'start' and 'build' commands must exist")

        self._local_repo: Optional[Repo] = None
        self._process: Optional[subprocess.Popen] = None
        self._host: str = "127.0.0.1"
        self._port: int = self._find_free_port()

        self.is_build_success: Optional[bool] = None
        self.is_start_success: Optional[bool] = None
        self.build_output: List[Dict[Literal["command", "output"], str]] = []
        self.start_output: Optional[List[str]] = []

        if self.path.exists():
            self._load_repo_from_path()
        else:
            self._clone_repo_from_remote()

    def _stream_process_output(self, stream):
        """Читает stdout/stderr построчно, сохраняет и отправляет в WS"""
        try:
            for raw_line in iter(stream.readline, ""):
                if raw_line is None:
                    break
                line = raw_line.rstrip("\n")
                if not line and stream.closed:
                    break

                self.start_output.append(line)  # сохраняем в историю

                if Tentacle._broadcast_logs:
                    try:
                        Tentacle._broadcast_logs(
                            self.name,
                            "start",
                            {"output": line},
                            stream=True  # помечаем, что это "живой" вывод
                        )
                    except Exception:
                        pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def get_logs(self, log_type):
        """Возвращает накопленные логи по типу"""
        if log_type == "build":
            return self.build_output
        if log_type == "start":
            return self.start_output
        return []

    def _load_repo_from_path(self):
        log(f"Found existing folder for branch '{self.name}'. Attempting to load...")
        try:
            self.local_repo = Repo(self.path)
            self.local_repo.refs[self.name].checkout(True)
            if self.update_required:
                log(f"Updating '{self.name}'")
                self._fetch_remote()

            log(f"Successfully loaded branch '{self.name}'.", "success")
        except Exception as e:
            log(f"Failed to load local repository for branch '{self.name}': {e}", "error")
            raise

    def _clone_repo_from_remote(self):
        log(f"Cloning branch '{self.name}' from remote...")
        try:
            self.local_repo = Repo.clone_from(
                self._repo_url,
                self.path,
                branch=self.name,
                depth=1,
                progress=progress
            )
            log(f"Successfully cloned branch '{self.name}'.", "success")
        except Exception as e:
            log(f"Failed to clone branch '{self.name}': {e}", "error")
            raise

    def update(self, clean: bool = False):
        self.stop()

        if clean:
            log(f"Updating tentacle '{self.name}' (clean)...")
            self.clear_files()
        else:
            log(f"Updating tentacle '{self.name}'...")

        if not self.path.exists() or self.local_repo is None:
            self._clone_repo_from_remote()
        else:
            self._fetch_remote()
        log(f"Tentacle '{self.name}' fetched!", "success")

        self.build()
        self.start()

    def _fetch_remote(self):
        log(f"Fetching tentacle '{self.name}'...")
        self.local_repo.remote().fetch(progress=progress, force=True)
        self.local_repo.remote().refs[self.name].checkout(True)

    def clear_files(self):
        log(f"Deleting tentacle '{self.name}' files...", "warning")
        if self._process is not None:
            raise RuntimeError("Cannot delete tentacle files while it's running")

        shutil.rmtree(self.path)

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
        self.build_output.clear()

        for raw_cmd in commands:
            if not raw_cmd.strip():
                continue

            cmd = self._render_command(raw_cmd)
            log(f"Running build step: '{cmd}'", log_type="info")

            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(self.path),
                    shell=True,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                stdout = result.stdout or ""
                stderr = result.stderr or ""
                if stdout.strip():
                    log(f"'{cmd}' output:\n{stdout.strip()}", "info")
                if stderr.strip():
                    log(f"'{cmd}' errors:\n{stderr.strip()}", "warning")
                self.build_output.append({"command": cmd, "output": stdout + ("\n" + stderr if stderr else "")})

                if Tentacle._broadcast_logs:
                    Tentacle._broadcast_logs(self.name, "build", self.build_output, stream=False)
            except subprocess.CalledProcessError as e:
                self.is_build_success = False
                out = (e.stdout or "") + ("\n" + (e.stderr or "")) if (e.stdout or e.stderr) else str(e)
                self.build_output.append({"command": cmd, "output": out})
                log(f"Build step failed:\n{e.stderr}", "error")
                break

        if Tentacle._broadcast_status:
            Tentacle._broadcast_status(self.name, self.is_build_success, self.is_start_success)
        if self.is_build_success:
            log(f"Tentacle '{self.name}' built successfully.", "success")

    def start(self):
        log(f"Starting tentacle '{self.name}'...")

        if self._process and self._process.poll() is None:
            log(f"Tentacle '{self.name}' is already running.", log_type="warning")
            return

        raw_cmd = self._commands.get("start")
        if not raw_cmd:
            log("No start command provided.", log_type="error")
            return

        cmd = self._render_command(raw_cmd)
        is_windows = platform.system() == "Windows"

        try:
            self.is_start_success = None
            if Tentacle._broadcast_status:
                Tentacle._broadcast_status(self.name, self.is_build_success, self.is_start_success)

            self.start_output.clear()

            self._process = subprocess.Popen(
                cmd,
                cwd=str(self.path),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0,
                preexec_fn=os.setsid if not is_windows else None
            )
            self.is_start_success = True
            log(f"Tentacle '{self.name}' started.", log_type="success")

            if Tentacle._broadcast_status:
                Tentacle._broadcast_status(self.name, self.is_build_success, self.is_start_success)

            if self._process.stdout:
                threading.Thread(target=self._stream_process_output, args=(self._process.stdout,), daemon=True).start()
            if self._process.stderr:
                threading.Thread(target=self._stream_process_output, args=(self._process.stderr,), daemon=True).start()

        except Exception as e:
            self.is_start_success = False
            self.start_output.append(str(e))
            log(f"Failed to start tentacle:\n{e}", log_type="error")
            if Tentacle._broadcast_status:
                Tentacle._broadcast_status(self.name, self.is_build_success, self.is_start_success)

    def stop(self):
        log(f"Stopping tentacle '{self.name}'...", log_type="header")

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

        self.is_start_success = None
        self.is_build_success = None

        if Tentacle._broadcast_status:
            Tentacle._broadcast_status(self.name, self.is_build_success, self.is_start_success)

        self._process = None

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    @property
    def local_repo(self) -> Repo | None:
        return self._local_repo

    @local_repo.setter
    def local_repo(self, value: Repo) -> None:
        self._local_repo = value
        self._local_repo.git.checkout(self.name, force=True)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def _repo_url(self) -> str | None:
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

        return self.remote_branch.commit.sha != self.local_repo.head.commit.hexsha

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
    def url(self) -> str | None:
        if self._port is None:
            return None
        return f"{self._host}:{self._port}"

    @property
    def last_commit(self) -> str:
        return self.local_repo.head.commit.hexsha[:7]

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
