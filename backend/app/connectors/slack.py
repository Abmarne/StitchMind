import requests
import datetime
from sqlalchemy.orm import Session
from app.database import Connector
from app.pipeline import process_and_index_document

def group_slack_messages(messages: list) -> list[dict]:
    """Groups message lists into conversational blocks (combining threads and time-proximity chats)."""
    if not messages:
        return []
    
    # Sort messages chronologically
    sorted_msgs = sorted(messages, key=lambda m: float(m.get("ts", 0)))
    
    threads = {}  # thread_ts -> list of messages
    standalone_conversations = []  # List of lists of contiguous messages
    
    # 1. Separate threaded messages and group normal ones by 1-hour time proximity
    current_block = []
    last_ts = None
    
    for msg in sorted_msgs:
        # Ignore bot join/leave events
        if msg.get("subtype") in ["channel_join", "channel_leave"]:
            continue
            
        thread_ts = msg.get("thread_ts")
        if thread_ts and thread_ts != msg.get("ts"):
            # This is a reply in a thread
            threads.setdefault(thread_ts, []).append(msg)
            continue
            
        # Is it a parent message of a thread?
        if msg.get("thread_ts") == msg.get("ts") and "reply_count" in msg:
            threads.setdefault(msg.get("ts"), []).append(msg)
            continue

        # Standalone message grouping by time proximity (1 hour = 3600 seconds)
        ts = float(msg.get("ts", 0))
        if last_ts is None or (ts - last_ts < 3600):
            current_block.append(msg)
        else:
            standalone_conversations.append(current_block)
            current_block = [msg]
        last_ts = ts
        
    if current_block:
        standalone_conversations.append(current_block)
        
    # Format grouped items
    results = []
    
    # Process threads
    for parent_ts, replies in threads.items():
        if not replies:
            continue
        first_msg = replies[0]
        # Build text description of thread
        body_lines = []
        authors = set()
        for r in replies:
            user = r.get("user") or r.get("username") or "Unknown"
            body_lines.append(f"@{user}: {r.get('text', '')}")
            authors.add(user)
            
        thread_time = datetime.datetime.fromtimestamp(float(parent_ts))
        results.append({
            "external_id": f"slack_thread_{parent_ts}",
            "title": f"Slack Thread in Channel ({len(replies)} messages)",
            "body": "\n".join(body_lines),
            "author": ", ".join(authors),
            "created_at": thread_time
        })
        
    # Process standalone blocks
    for idx, block in enumerate(standalone_conversations):
        if not block:
            continue
        first_msg = block[0]
        body_lines = []
        authors = set()
        for msg in block:
            user = msg.get("user") or msg.get("username") or "Unknown"
            body_lines.append(f"@{user}: {msg.get('text', '')}")
            authors.add(user)
            
        block_time = datetime.datetime.fromtimestamp(float(first_msg.get("ts", 0)))
        results.append({
            "external_id": f"slack_block_{first_msg.get('ts')}",
            "title": f"Slack Conversation Block ({len(block)} messages)",
            "body": "\n".join(body_lines),
            "author": ", ".join(authors),
            "created_at": block_time
        })
        
    return results

def sync_slack(db: Session, connector: Connector):
    """Fetches history for designated channels and stores them as consolidated threads."""
    auth_config = connector.get_auth_config()
    token = auth_config.get("token")
    channels = auth_config.get("channels", [])  # List of channel IDs (e.g. ["C123456"])
    
    if not token or not channels:
        raise ValueError("Slack connector config requires 'token' and 'channels' list")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    for channel in channels:
        history_url = f"https://slack.com/api/conversations.history?channel={channel}&limit=50"
        try:
            response = requests.get(history_url, headers=headers, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                if not res_data.get("ok"):
                    print(f"Slack API error for channel {channel}: {res_data.get('error')}")
                    continue
                    
                raw_messages = res_data.get("messages", [])
                grouped = group_slack_messages(raw_messages)
                
                for group in grouped:
                    # Append channel metadata to url / title
                    url = f"https://slack.com/archives/{channel}/{group['external_id'].split('_')[-1]}"
                    process_and_index_document(
                        db=db,
                        connector_id=connector.id,
                        external_id=group["external_id"],
                        platform="slack",
                        title=f"{group['title']} [Channel: {channel}]",
                        body=group["body"],
                        url=url,
                        author=group["author"],
                        created_at=group["created_at"]
                    )
            else:
                print(f"Slack Sync warning: API returned status {response.status_code}")
        except Exception as e:
            print(f"Error syncing Slack channel {channel}: {e}")
