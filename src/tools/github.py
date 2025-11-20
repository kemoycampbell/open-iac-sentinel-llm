import requests
import subprocess
import os

# List all open PRs with the given labels
def list_drifted_prs(owner: str, repo: str, token: str, labels: list):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    headers = {
        "Authorization": f"token {token}"
    }

    params = {
        "state": "open",
        "labels": ",".join(labels)
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    prs = [pr for pr in response.json() if 'pull_request' in pr]

    return {
        "drifted_prs": prs
    }

# Stage files in Git
def stage_change(repo_dir: str, files: list):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        # Add files to staging
        result = subprocess.run(["git", "add"] + files, capture_output=True, text=True)

        return {
            "stage_change_result_code": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip()
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git add failed: {e.cmd} with returncode {e.returncode}",
            "output": e.output,
            "stderr": e.stderr
        }

    finally:
        os.chdir(cwd)

# Commit changes in Git
def commit_change(repo_dir: str, message: str):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)

        return {
            "commit_change_result_code": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip()
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git commit failed: {e.cmd} with returncode {e.returncode}",
            "output": e.output,
            "stderr": e.stderr
        }

    finally:
        os.chdir(cwd)

# Push changes to remote branch
def push_change(repo_dir: str, branch: str):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        # Push branch, set upstream if branch does not exist remotely
        result = subprocess.run(["git", "push", "--set-upstream", "origin", branch],
                                capture_output=True, text=True)

        return {
            "push_change_result_code": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip()
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git push failed: {e.cmd} with returncode {e.returncode}",
            "output": e.output,
            "stderr": e.stderr
        }

    finally:
        os.chdir(cwd)

# Find the main branch of the repo
def find_main_branch(repo_dir: str):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        result = subprocess.run(
            ["git", "remote", "show", "origin"],
            capture_output=True, text=True
        )

        for line in result.stdout.splitlines():
            if "HEAD branch" in line:
                main_branch = line.split(":")[-1].strip()
                return {"main_branch": main_branch}

        # fallback if parsing fails
        return {"main_branch": result.stdout.strip()}

    finally:
        os.chdir(cwd)

# Get repo owner and name from Git remote URL
def find_repo_name_and_owner(repo_dir: str):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        result = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                                capture_output=True, text=True)
        url = result.stdout.strip()

        if url.endswith('.git'):
            url = url[:-4]

        info = url.split('/')[-2:]
        return {"owner": info[0], "repo": info[1]}

    finally:
        os.chdir(cwd)

def create_branch(repo_dir: str, base_branch: str, new_branch: str):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)

        # Checkout base branch and pull latest
        subprocess.run(["git", "checkout", base_branch], check=True, capture_output=True, text=True)
        subprocess.run(["git", "pull", "origin", base_branch], check=True, capture_output=True, text=True)

        # Check if new_branch exists
        result = subprocess.run(["git", "branch", "--list", new_branch],
                                capture_output=True, text=True, check=True)
        if result.stdout.strip():
            # Branch exists, just checkout
            checkout_result = subprocess.run(["git", "checkout", new_branch],
                                             check=True, capture_output=True, text=True)
        else:
            # Branch does not exist, create it
            checkout_result = subprocess.run(["git", "checkout", "-b", new_branch],
                                             check=True, capture_output=True, text=True)

        # Verify the branch exists locally
        verify = subprocess.run(["git", "rev-parse", "--verify", new_branch],
                                check=True, capture_output=True, text=True)

        return {
            "create_branch_result_code": checkout_result.returncode,
            "branch": new_branch,
            "output": checkout_result.stdout.strip(),
            "error": checkout_result.stderr.strip()
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git command failed: {e.cmd} with returncode {e.returncode}",
            "output": e.output,
            "stderr": e.stderr
        }

    finally:
        os.chdir(cwd)


# Delete a branch locally
def delete_branch(repo_dir: str, branch: str):
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        main = find_main_branch(repo_dir)["main_branch"]
        subprocess.run(["git", "checkout", main], capture_output=True, text=True)
        result = subprocess.run(["git", "branch", "-D", branch], capture_output=True, text=True)
        return {
            "delete_branch_result_code": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip()
        }

    except subprocess.CalledProcessError as e:
        return {
            "error": f"Git delete branch failed: {e.cmd} with returncode {e.returncode}",
            "output": e.output,
            "stderr": e.stderr
        }

    finally:
        os.chdir(cwd)

# Create a pull request on GitHub
def create_pr(repo: str, token: str, owner: str, title: str, body: str, head: str, base: str):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"token {token}",
    }

    payload = {
        "title": title,
        "head": head,
        "base": base,
        "body": body
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 201:
        pr_data = response.json()
        return {"status": "success", "pr_url": pr_data['html_url']}
    else:
        return {"status": "error", "message": response.json()}
