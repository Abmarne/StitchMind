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
                pr_number = pr["number"]
                
                # Fetch Commits
                commits_url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/commits"
                commits_res = requests.get(commits_url, headers=headers, timeout=15)
                commits_text = ""
                if commits_res.status_code == 200:
                    for c in commits_res.json():
                        c_msg = c.get("commit", {}).get("message", "")
                        commits_text += f"\n- {c_msg}"
                if commits_text:
                    commits_text = f"\n\n--- Commits ---{commits_text}"

                # Fetch Comments
                comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
                comments_res = requests.get(comments_url, headers=headers, timeout=15)
                comments_text = ""
                if comments_res.status_code == 200:
                    for c in comments_res.json():
                        c_author = c.get("user", {}).get("login", "Unknown")
                        c_body = c.get("body", "")
                        comments_text += f"\n\n--- Comment by {c_author} ---\n{c_body}"
                
                # Labels
                labels = [label["name"] for label in pr.get("labels", [])]
                labels_str = f"Labels: {', '.join(labels)}\n\n" if labels else ""
                
                base_body = pr.get("body") or "No description provided."
                full_body = f"{labels_str}{base_body}{commits_text}{comments_text}"
                
                created_at = datetime.datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                process_and_index_document(
                    db=db,
                    connector_id=connector.id,
                    external_id=str(pr_number),
                    platform="github",
                    title=f"PR #{pr_number}: {pr['title']}",
                    body=full_body,
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
                    
                issue_number = issue["number"]
                
                # Fetch Comments
                comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
                comments_res = requests.get(comments_url, headers=headers, timeout=15)
                comments_text = ""
                if comments_res.status_code == 200:
                    for c in comments_res.json():
                        c_author = c.get("user", {}).get("login", "Unknown")
                        c_body = c.get("body", "")
                        comments_text += f"\n\n--- Comment by {c_author} ---\n{c_body}"
                
                # Labels
                labels = [label["name"] for label in issue.get("labels", [])]
                labels_str = f"Labels: {', '.join(labels)}\n\n" if labels else ""
                
                base_body = issue.get("body") or "No description provided."
                full_body = f"{labels_str}{base_body}{comments_text}"

                created_at = datetime.datetime.strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                process_and_index_document(
                    db=db,
                    connector_id=connector.id,
                    external_id=str(issue_number),
                    platform="github",
                    title=f"Issue #{issue_number}: {issue['title']}",
                    body=full_body,
                    url=issue["html_url"],
                    author=issue["user"]["login"],
                    created_at=created_at
                )
        else:
            print(f"GitHub Issue Sync warning: API returned status {response.status_code}")
    except Exception as e:
        print(f"Error syncing GitHub Issues: {e}")
