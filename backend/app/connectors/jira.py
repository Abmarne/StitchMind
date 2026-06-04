import requests
import datetime
from sqlalchemy.orm import Session
from app.database import Connector
from app.pipeline import process_and_index_document

def parse_adf_description(node) -> str:
    """Recursively parses Atlassian Document Format (ADF) JSON structure into plain text."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "text":
            return node.get("text", "")
        # Handle list structures, paragraph spaces
        prefix = ""
        if node_type == "paragraph":
            prefix = "\n"
        elif node_type == "listItem":
            prefix = "\n- "
            
        child_text = ""
        for child in node.get("content", []):
            child_text += parse_adf_description(child)
            
        return prefix + child_text
    return ""

def sync_jira(db: Session, connector: Connector):
    """Fetches tickets from Jira Cloud using Basic auth and custom JQL searches."""
    auth_config = connector.get_auth_config()
    domain = auth_config.get("domain")       # E.g. "company.atlassian.net"
    email = auth_config.get("email")
    api_token = auth_config.get("api_token")
    jql = auth_config.get("jql", "updated >= -30d")
    
    if not domain or not email or not api_token:
        raise ValueError("Jira config requires 'domain', 'email', and 'api_token'")

    url = f"https://{domain}/rest/api/3/search"
    headers = {
        "Accept": "application/json"
    }
    params = {
        "jql": jql,
        "maxResults": 20
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            auth=(email, api_token),
            timeout=15
        )
        if response.status_code == 200:
            res_data = response.json()
            issues = res_data.get("issues", [])
            for issue in issues:
                key = issue.get("key")
                fields = issue.get("fields", {})
                summary = fields.get("summary", "")
                
                # Parse description (ADF structure in v3 API)
                description_raw = fields.get("description")
                description_text = parse_adf_description(description_raw)
                if not description_text.strip():
                    description_text = "No description provided."
                    
                status = fields.get("status", {}).get("name", "Unknown")
                assignee_info = fields.get("assignee")
                assignee_name = assignee_info.get("displayName") if assignee_info else "Unassigned"
                
                body = (
                    f"Ticket Key: {key}\n"
                    f"Status: {status}\n"
                    f"Assignee: {assignee_name}\n"
                    f"Summary: {summary}\n"
                    f"Description: {description_text}"
                )
                
                ticket_url = f"https://{domain}/browse/{key}"
                
                # Parse creation timestamp
                created_str = fields.get("created", "")
                created_at = datetime.datetime.utcnow()
                if created_str:
                    try:
                        # "2026-06-04T12:00:00.000+0530" -> trim and load ISO
                        created_at = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00")[:19])
                    except Exception:
                        pass

                process_and_index_document(
                    db=db,
                    connector_id=connector.id,
                    external_id=key,
                    platform="jira",
                    title=f"{key}: {summary}",
                    body=body,
                    url=ticket_url,
                    author=assignee_name,
                    created_at=created_at
                )
        else:
            print(f"Jira Sync warning: API returned status {response.status_code} ({response.text})")
    except Exception as e:
        print(f"Error syncing Jira: {e}")
