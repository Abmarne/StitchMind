import os
import base64
import datetime
from sqlalchemy.orm import Session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.database import Connector
from app.pipeline import process_and_index_document
from app.config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKENS_FILE

# Scopes for reading Gmail messages and Google Docs via Drive API
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

def get_google_creds() -> Credentials:
    """Retrieves Google API credentials, running local OAuth loopback if needed."""
    creds = None
    if os.path.exists(GOOGLE_TOKENS_FILE):
        try:
            creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKENS_FILE), SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Google oauth credentials client secret missing at {GOOGLE_CREDENTIALS_FILE}. "
                    "Download the credentials.json from Google Cloud Console."
                )
            
            # Spin up local browser flow
            flow = InstalledAppFlow.from_client_secrets_file(
                str(GOOGLE_CREDENTIALS_FILE), SCOPES
            )
            # Starts local web server on port 8080 to receive auth code
            creds = flow.run_local_server(
                port=8080, 
                authorization_prompt_message="StitchMind: Authorizing Google Docs & Gmail Access...",
                success_message="Google authentication completed. You can close this window now!"
            )

        # Save authorized user credentials
        with open(GOOGLE_TOKENS_FILE, "w") as token_file:
            token_file.write(creds.to_json())

    return creds

def sync_gmail(db: Session, connector: Connector):
    """Retrieves recent Gmail messages and index them."""
    try:
        creds = get_google_creds()
        service = build("gmail", "v1", credentials=creds)
        
        # Fetch list of messages from the last 2 days
        today = datetime.date.today()
        two_days_ago = today - datetime.timedelta(days=2)
        q = f"after:{two_days_ago.strftime('%Y/%m/%d')}"
        
        results = service.users().messages().list(userId="me", q=q, maxResults=10).execute()
        messages = results.get("messages", [])
        
        for msg_meta in messages:
            msg_id = msg_meta["id"]
            msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            
            # Extract Headers
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            subject = "No Subject"
            sender = "Unknown Sender"
            date_str = ""
            for h in headers:
                name = h.get("name", "").lower()
                if name == "subject":
                    subject = h.get("value", "")
                elif name == "from":
                    sender = h.get("value", "")
                elif name == "date":
                    date_str = h.get("value", "")

            # Extract body
            body_text = ""
            parts = payload.get("parts", [])
            
            def extract_body(part_list):
                text = ""
                for part in part_list:
                    mime = part.get("mimeType", "")
                    body_data = part.get("body", {}).get("data", "")
                    if mime == "text/plain" and body_data:
                        text += base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
                    elif part.get("parts"):
                        text += extract_body(part.get("parts"))
                return text

            if parts:
                body_text = extract_body(parts)
            else:
                body_data = payload.get("body", {}).get("data", "")
                if body_data:
                    body_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")

            if not body_text.strip():
                body_text = "No content plain text body found."

            # Date parsing
            created_at = datetime.datetime.utcnow()
            if date_str:
                try:
                    # Parse standard RFC email date
                    # Sat, 15 Jun 2024 10:11:12 -0000
                    # We fallback to standard datetime parse if failure
                    # Cut timezone offset to avoid complexity
                    created_at = datetime.datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                except Exception:
                    pass

            email_url = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"
            
            process_and_index_document(
                db=db,
                connector_id=connector.id,
                external_id=msg_id,
                platform="gmail",
                title=f"Email: {subject}",
                body=f"Sender: {sender}\nSubject: {subject}\nDate: {date_str}\n\n{body_text}",
                url=email_url,
                author=sender,
                created_at=created_at
            )
            
    except Exception as e:
        print(f"Error syncing Gmail: {e}")

def sync_google_docs(db: Session, connector: Connector):
    """Retrieves recent Google Docs updated in the last 7 days."""
    try:
        creds = get_google_creds()
        drive_service = build("drive", "v3", credentials=creds)
        
        # Search for files with application/vnd.google-apps.document mime type
        query = "mimeType = 'application/vnd.google-apps.document' and trashed = false"
        results = drive_service.files().list(
            q=query, 
            pageSize=10, 
            fields="files(id, name, webViewLink, owners, modifiedTime)"
        ).execute()
        files = results.get("files", [])
        
        for file in files:
            file_id = file["id"]
            name = file["name"]
            web_link = file.get("webViewLink", "")
            
            # Extract owner display name
            owners = file.get("owners", [])
            owner_name = owners[0].get("displayName", "Unknown") if owners else "Unknown Owner"
            
            # Export Docs to raw text
            try:
                content_bytes = drive_service.files().export(
                    fileId=file_id, 
                    mimeType="text/plain"
                ).execute()
                body_text = content_bytes.decode("utf-8")
            except Exception as e:
                print(f"Drive export text/plain failed for doc {file_id}: {e}")
                body_text = "Failed to export document body contents."

            # Date parsing
            modified_time_str = file.get("modifiedTime", "")
            created_at = datetime.datetime.utcnow()
            if modified_time_str:
                try:
                    created_at = datetime.datetime.fromisoformat(modified_time_str.replace("Z", "+00:00")[:19])
                except Exception:
                    pass

            process_and_index_document(
                db=db,
                connector_id=connector.id,
                external_id=file_id,
                platform="google_workspace",  # Google Docs
                title=f"Google Doc: {name}",
                body=f"Document Name: {name}\nOwner: {owner_name}\n\n{body_text}",
                url=web_link,
                author=owner_name,
                created_at=created_at
            )

    except Exception as e:
        print(f"Error syncing Google Docs: {e}")
