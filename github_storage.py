"""
GitHub-based CSV Storage Module

Provides read/write access to CSV files stored in the GitHub repository,
allowing data to persist across Streamlit Cloud reboots.

Requires a GitHub Personal Access Token (PAT) with 'repo' scope stored in
Streamlit secrets as GITHUB_TOKEN.

Usage:
    from github_storage import read_csv_from_github, write_csv_to_github

    # Read a CSV file
    df = read_csv_from_github("data/prediction_log.csv")

    # Write a CSV file
    write_csv_to_github(df, "data/prediction_log.csv", "Update predictions")
"""
import pandas as pd
import requests
import base64
from typing import Optional
from io import StringIO
import streamlit as st


def get_github_config() -> dict:
    """
    Get GitHub configuration from Streamlit secrets.

    Expected secrets structure:
    [github]
    token = "ghp_..."
    repo = "username/repo-name"
    branch = "main"
    """
    try:
        return {
            "token": st.secrets["github"]["token"],
            "repo": st.secrets["github"]["repo"],
            "branch": st.secrets["github"].get("branch", "main"),
        }
    except Exception:
        return None


def read_csv_from_github(file_path: str) -> Optional[pd.DataFrame]:
    """
    Read a CSV file from the GitHub repository.

    Args:
        file_path: Path to the file in the repo (e.g., "data/prediction_log.csv")

    Returns:
        DataFrame or None if file doesn't exist or error occurs
    """
    config = get_github_config()
    if config is None:
        return None

    url = f"https://api.github.com/repos/{config['repo']}/contents/{file_path}"
    headers = {
        "Authorization": f"token {config['token']}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {"ref": config["branch"]}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 404:
            # File doesn't exist yet
            return None

        response.raise_for_status()
        data = response.json()

        # Decode base64 content
        content = base64.b64decode(data["content"]).decode("utf-8")

        # Parse CSV
        df = pd.read_csv(StringIO(content))
        return df

    except Exception as e:
        print(f"Error reading from GitHub: {e}")
        return None


def get_file_sha(file_path: str, config: dict) -> Optional[str]:
    """
    Get the SHA of an existing file (required for updates).

    Returns None if file doesn't exist.
    """
    url = f"https://api.github.com/repos/{config['repo']}/contents/{file_path}"
    headers = {
        "Authorization": f"token {config['token']}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {"ref": config["branch"]}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get("sha")
        return None
    except Exception:
        return None


def write_csv_to_github(
    df: pd.DataFrame,
    file_path: str,
    commit_message: str = "Update data"
) -> bool:
    """
    Write a DataFrame to a CSV file in the GitHub repository.

    Args:
        df: DataFrame to write
        file_path: Path in the repo (e.g., "data/prediction_log.csv")
        commit_message: Commit message for the change

    Returns:
        True if successful, False otherwise
    """
    config = get_github_config()
    if config is None:
        print("GitHub config not found in secrets")
        return False

    url = f"https://api.github.com/repos/{config['repo']}/contents/{file_path}"
    headers = {
        "Authorization": f"token {config['token']}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Convert DataFrame to CSV string, then base64
    csv_content = df.to_csv(index=False)
    content_base64 = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")

    # Build the request payload
    payload = {
        "message": commit_message,
        "content": content_base64,
        "branch": config["branch"],
    }

    # Get existing file SHA if updating
    sha = get_file_sha(file_path, config)
    if sha:
        payload["sha"] = sha

    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return True

    except Exception as e:
        print(f"Error writing to GitHub: {e}")
        return False


def file_exists_on_github(file_path: str) -> bool:
    """
    Check if a file exists in the GitHub repository.

    Args:
        file_path: Path to check (e.g., "data/prediction_log.csv")

    Returns:
        True if file exists, False otherwise
    """
    config = get_github_config()
    if config is None:
        return False

    return get_file_sha(file_path, config) is not None


def github_storage_available() -> bool:
    """
    Check if GitHub storage is configured and accessible.

    Returns:
        True if GitHub token and repo are configured
    """
    config = get_github_config()
    return config is not None and config.get("token") and config.get("repo")


if __name__ == "__main__":
    # Test module (requires secrets to be configured)
    print("GitHub Storage Module")
    print("=" * 40)

    if github_storage_available():
        print("GitHub storage is configured")

        # Test read
        df = read_csv_from_github("data/prediction_log.csv")
        if df is not None:
            print(f"Read {len(df)} rows from prediction_log.csv")
        else:
            print("prediction_log.csv not found or empty")
    else:
        print("GitHub storage not configured (missing secrets)")
