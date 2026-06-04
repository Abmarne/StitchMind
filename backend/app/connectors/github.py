import requests
import datetime
from sqlalchemy.orm import Session
from app.database import Connector
from app.pipeline import process_and_index_document

def sync_github(db: Session, connector: Connector):
    """Synchronizes open and closed pull requests and issues from a configured GitHub repository."""
    auth_config = connector.get_auth_config()
    token = auth_config.get("token")
    repo = auth_config.get("repo")  # E.g. "owner/repo"
    
    if not token or not repo:
        raise ValueError("GitHub connector config requires 'token' and 'repo'")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Fetch Pull Requests
    prs_url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=10"
    try:
        response = requests.get(prs_url, headers=headers, timeout=15)
        if response.status_code == 200:
            prs = response.json()
            for pr in prs:
                created_at = datetime.datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                process_and_index_document(
                    db=db,
                    connector_id=connector.id,
                    external_id=str(pr["number"]),
                    platform="github",
                    title=f"PR #{pr['number']}: {pr['title']}",
                    body=pr.get("body") or "No description provided.",
                    url=pr["html_url"],
                    author=pr["user"]["login"],
                    created_at=created_at
                )
        else:
            print(f"GitHub PR Sync warning: API returned status {response.status_code} ({response.text})")
    except Exception as e:
        print(f"Error syncing GitHub PRs: {e}")

    # 2. Fetch Issues
    issues_url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=10"
    try:
        response = requests.get(issues_url, headers=headers, timeout=15)
        if response.status_code == 200:
            issues = response.json()
            for issue in issues:
                # GitHub issues endpoint includes pull requests, so skip them
                if "pull_request" in issue:
                    continue
                created_at = datetime.datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                process_and_index_document(
                    db=db,
                    connector_id=connector.id,
                    external_id=str(issue["number"]),
                    platform="github",
                    title=f"Issue #{issue['number']}: {issue['title']}",
                    body=issue.get("body") or "No description provided.",
                    url=issue["html_url"],
                    author=issue["user"]["login"],
                    created_at=created_at
                )
        else:
            print(f"GitHub Issue Sync warning: API returned status {response.status_code}")
    except Exception as e:
        print(f"Error syncing GitHub Issues: {e}")
