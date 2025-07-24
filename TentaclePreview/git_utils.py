import requests
from typing import List, Literal
import os
import shutil
from git import Repo, GitCommandError


def get_github_repo_branches(repo_url: str,
                             github_token: str | None = None,
                             filter_mode: Literal["exclude", "include"] = "exclude",
                             filter_branches: List[str] = None) -> List[str]:
    match filter_mode:
        case "exclude":
            branch_filter = lambda branch: branch not in filter_branches
        case "include":
            branch_filter = lambda branch: branch in filter_branches
        case _:
            raise ValueError(f"Invalid filter mode: {filter_mode}")

    if not repo_url.startswith('https://github.com/'):
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}. Must start with 'https://github.com/'")

    parts = repo_url.strip('/').split('/')
    if len(parts) < 5:
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}. Cannot parse owner and repo name.")

    owner = parts[-2]
    repo = parts[-1]

    api_url = f"https://api.github.com/repos/{owner}/{repo}/branches"

    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    response = requests.get(api_url, headers=headers)
    response.raise_for_status()

    branches = [branch['name'] for branch in response.json()]
    branches = list(filter(branch_filter, branches))

    return branches


def update_repo(repo_url, clone_dir="repo_temp"):
    """Клонирует или обновляет репозиторий с принудительным fetch."""
    try:
        if os.path.exists(clone_dir):
            print(f"Репозиторий уже существует. Делаем fetch --force...")
            repo = Repo(clone_dir)
            repo.git.fetch("--all", "--force", "--prune")
        else:
            print(f"Клонируем репозиторий {repo_url}...")
            repo = Repo.clone_from(repo_url, clone_dir)
        return repo
    except GitCommandError as e:
        print(f"Ошибка при работе с git: {e}")
        raise


def copy_branch_files(repo, branch, target_dir):
    """Копирует файлы из указанной ветки в целевую папку, исключая .git."""
    # Создаем папку (включая вложенные для branch с '/')
    os.makedirs(target_dir, exist_ok=True)

    # Переключаемся на ветку (без проверки изменений)
    repo.git.checkout("--force", branch)
    repo.git.clean("-fd")  # Удаляем неотслеживаемые файлы

    # Копируем всё, кроме .git
    for item in os.listdir(repo.working_dir):
        if item == ".git":
            continue
        src = os.path.join(repo.working_dir, item)
        dst = os.path.join(target_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def setup_branches(repo_url, branches, output_dir="branches"):
    """
    Основная функция:
    - repo_url: URL репозитория (например, "https://github.com/user/repo.git")
    - branches: список имен веток (например, ["main", "dev", "feat/new-logo"])
    - output_dir: корневая папка для веток.
    """
    repo = update_repo(repo_url)

    for branch in branches:
        branch_dir = os.path.join(output_dir, *branch.split("/"))
        print(f"Обрабатываем ветку: {branch} -> {branch_dir}")
        copy_branch_files(repo, branch, branch_dir)

    print("Готово! Все ветки сохранены.")


if __name__ == "__main__":
    import json

    config = json.load(open("./../config.json"))
    repo_url = config["repo_url"]
    token = config["github_token"]
    branches = get_github_repo_branches(repo_url, token, config["filter_mode"], config["filter_branches"])

    if branches:
        print("Ветки репозитория:")
        for branch in branches:
            print(f"- {branch}")
    else:
        print("Не удалось получить список веток.")


    repo_url = "https://github.com/example_user/example_repo.git"
    branches = ["main", "dev", "feat/new-logo"]
    setup_branches(repo_url, branches)
