"""icloud-mail-manager MCP server.

This server exposes iCloud Mail management tools over MCP using IMAP and SMTP.
"""

from __future__ import annotations

import imaplib
import mimetypes
import os
import re
import smtplib
import socket
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage, Message
from email.utils import parsedate_to_datetime
from pathlib import Path
import sys
from typing import Any, Generator, Literal

try:
    from dotenv import load_dotenv
except ImportError:
    # Allow startup even if python-dotenv is unavailable; environment variables can still be provided by the host.
    def load_dotenv() -> bool:  # type: ignore[misc]
        print(
            "[icloud-mail-manager] python-dotenv is not installed; skipping .env loading.",
            file=sys.stderr,
        )
        return False

from mcp.server.fastmcp import FastMCP


IMAP_HOST = "imap.mail.me.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.mail.me.com"
SMTP_PORT = 587
DEFAULT_TIMEOUT = 30

AccountMode = Literal["PRIVATE", "BUSINESS", "MIXED"]


class ICloudMailError(Exception):
    """Raised when a mail operation fails."""


@dataclass(frozen=True)
class MailConfig:
    email_address: str
    app_password: str
    account_mode: AccountMode
    timeout: int = DEFAULT_TIMEOUT
    imap_host: str = IMAP_HOST
    imap_port: int = IMAP_PORT
    smtp_host: str = SMTP_HOST
    smtp_port: int = SMTP_PORT


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        if isinstance(raw, str):
            return raw
        return ""

    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _sanitize_filename(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return safe or "attachment.bin"


def _parse_iso_date(value: str) -> str:
    """Convert YYYY-MM-DD date into IMAP date format DD-Mon-YYYY."""
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.strftime("%d-%b-%Y")


class ICloudMailClient:
    def __init__(self, config: MailConfig) -> None:
        self.config = config

    @contextmanager
    def imap_session(self) -> Generator[imaplib.IMAP4_SSL, None, None]:
        client: imaplib.IMAP4_SSL | None = None
        try:
            client = imaplib.IMAP4_SSL(
                self.config.imap_host,
                self.config.imap_port,
                timeout=self.config.timeout,
            )
            client.login(self.config.email_address, self.config.app_password)
            yield client
        except (imaplib.IMAP4.error, TimeoutError, socket.timeout, OSError) as exc:
            raise ICloudMailError(f"IMAP connection error: {exc}") from exc
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass

    @contextmanager
    def smtp_session(self) -> Generator[smtplib.SMTP, None, None]:
        client: smtplib.SMTP | None = None
        try:
            client = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=self.config.timeout)
            client.starttls()
            client.login(self.config.email_address, self.config.app_password)
            yield client
        except (smtplib.SMTPException, TimeoutError, socket.timeout, OSError) as exc:
            raise ICloudMailError(f"SMTP connection error: {exc}") from exc
        finally:
            if client is not None:
                try:
                    client.quit()
                except Exception:
                    pass

    def _ensure_ok(self, status: str, data: Any, message: str) -> None:
        if status != "OK":
            details = data.decode() if isinstance(data, bytes) else str(data)
            raise ICloudMailError(f"{message}: {details}")

    def _parse_mailbox_line(self, raw_line: bytes) -> dict[str, Any] | None:
        line = raw_line.decode(errors="replace")
        match = re.match(r"\((?P<flags>[^)]*)\) \"(?P<delimiter>[^\"]+)\" (?P<name>.+)", line)
        if not match:
            return None

        raw_name = match.group("name").strip()
        if raw_name.startswith('"') and raw_name.endswith('"'):
            name = raw_name[1:-1]
        else:
            name = raw_name

        flags = [flag for flag in match.group("flags").split() if flag]
        return {
            "name": name,
            "delimiter": match.group("delimiter"),
            "flags": flags,
        }

    def _extract_message_bytes(self, fetch_data: list[Any]) -> bytes:
        for item in fetch_data:
            if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
                return item[1]
        raise ICloudMailError("No message payload found.")

    def _extract_bodies(self, message: Message) -> tuple[str, str]:
        text_parts: list[str] = []
        html_parts: list[str] = []

        if message.is_multipart():
            for part in message.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                content_disposition = (part.get("Content-Disposition") or "").lower()
                if "attachment" in content_disposition:
                    continue

                content_type = (part.get_content_type() or "").lower()
                decoded = _decode_payload(part)
                if content_type == "text/plain":
                    text_parts.append(decoded)
                elif content_type == "text/html":
                    html_parts.append(decoded)
        else:
            content_type = (message.get_content_type() or "").lower()
            decoded = _decode_payload(message)
            if content_type == "text/html":
                html_parts.append(decoded)
            else:
                text_parts.append(decoded)

        return "\n".join(text_parts).strip(), "\n".join(html_parts).strip()

    def _extract_attachments(self, message: Message) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []

        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue

            filename = part.get_filename()
            content_disposition = (part.get("Content-Disposition") or "").lower()
            is_attachment = filename is not None or "attachment" in content_disposition
            if not is_attachment:
                continue

            payload = part.get_payload(decode=True) or b""
            attachments.append(
                {
                    "filename": _decode_header(filename) if filename else "attachment.bin",
                    "content_type": part.get_content_type(),
                    "size_bytes": len(payload),
                    "payload": payload,
                }
            )

        return attachments

    def list_folders(self) -> dict[str, Any]:
        with self.imap_session() as imap:
            status, data = imap.list()
            self._ensure_ok(status, data, "Unable to list folders")

            folders: list[dict[str, Any]] = []
            delimiter = "/"

            for line in data:
                if not isinstance(line, bytes):
                    continue
                parsed = self._parse_mailbox_line(line)
                if not parsed:
                    continue
                folders.append(parsed)
                delimiter = parsed["delimiter"]

            tree: dict[str, Any] = {}
            for folder in folders:
                node = tree
                for part in folder["name"].split(delimiter):
                    node = node.setdefault(part, {})

            return {
                "ok": True,
                "delimiter": delimiter,
                "folders": folders,
                "tree": tree,
            }

    def manage_folder(
        self,
        action: Literal["create", "rename", "delete"],
        folder_name: str,
        new_name: str | None = None,
    ) -> dict[str, Any]:
        with self.imap_session() as imap:
            if action == "create":
                status, data = imap.create(folder_name)
                self._ensure_ok(status, data, f"Unable to create folder '{folder_name}'")
                return {"ok": True, "message": f"Folder created: {folder_name}"}

            if action == "rename":
                if not new_name:
                    raise ICloudMailError("new_name is required when action is 'rename'.")
                status, data = imap.rename(folder_name, new_name)
                self._ensure_ok(status, data, f"Unable to rename folder '{folder_name}'")
                return {
                    "ok": True,
                    "message": f"Folder renamed: {folder_name} -> {new_name}",
                }

            if action == "delete":
                status, data = imap.delete(folder_name)
                self._ensure_ok(status, data, f"Unable to delete folder '{folder_name}'")
                return {"ok": True, "message": f"Folder deleted: {folder_name}"}

            raise ICloudMailError(f"Unsupported action: {action}")

    def search_emails(
        self,
        folder: str,
        from_address: str | None,
        subject: str | None,
        since: str | None,
        before: str | None,
        keyword: str | None,
        limit: int,
    ) -> dict[str, Any]:
        with self.imap_session() as imap:
            status, data = imap.select(folder, readonly=True)
            self._ensure_ok(status, data, f"Unable to select folder '{folder}'")

            criteria: list[str] = ["ALL"]
            if from_address:
                criteria.extend(["FROM", f'"{from_address}"'])
            if subject:
                criteria.extend(["SUBJECT", f'"{subject}"'])
            if since:
                criteria.extend(["SINCE", _parse_iso_date(since)])
            if before:
                criteria.extend(["BEFORE", _parse_iso_date(before)])
            if keyword:
                criteria.extend(["TEXT", f'"{keyword}"'])

            status, data = imap.uid("SEARCH", None, *criteria)
            self._ensure_ok(status, data, "Unable to search emails")

            uid_list = data[0].decode().split() if data and data[0] else []
            selected_uids = list(reversed(uid_list))[: max(limit, 1)]

            results: list[dict[str, Any]] = []
            for uid in selected_uids:
                fetch_status, fetch_data = imap.uid(
                    "FETCH",
                    uid,
                    "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE TO)])",
                )
                if fetch_status != "OK" or not fetch_data:
                    continue

                try:
                    header_bytes = self._extract_message_bytes(fetch_data)
                    message = message_from_bytes(header_bytes)
                    results.append(
                        {
                            "uid": uid,
                            "from": _decode_header(message.get("From")),
                            "to": _decode_header(message.get("To")),
                            "subject": _decode_header(message.get("Subject")),
                            "date": _decode_header(message.get("Date")),
                        }
                    )
                except Exception:
                    continue

            return {
                "ok": True,
                "folder": folder,
                "criteria": criteria,
                "total_matches": len(uid_list),
                "returned": len(results),
                "emails": results,
            }

    def read_email(self, folder: str, uid: str) -> dict[str, Any]:
        with self.imap_session() as imap:
            status, data = imap.select(folder, readonly=True)
            self._ensure_ok(status, data, f"Unable to select folder '{folder}'")

            status, data = imap.uid("FETCH", uid, "(RFC822)")
            self._ensure_ok(status, data, f"Unable to fetch email UID {uid}")

            raw_message = self._extract_message_bytes(data)
            message = message_from_bytes(raw_message)
            text_body, html_body = self._extract_bodies(message)
            attachments = self._extract_attachments(message)

            parsed_date = _decode_header(message.get("Date"))
            iso_date: str | None = None
            if parsed_date:
                try:
                    iso_date = parsedate_to_datetime(parsed_date).isoformat()
                except Exception:
                    iso_date = None

            return {
                "ok": True,
                "uid": uid,
                "folder": folder,
                "subject": _decode_header(message.get("Subject")),
                "from": _decode_header(message.get("From")),
                "to": _decode_header(message.get("To")),
                "cc": _decode_header(message.get("Cc")),
                "date": parsed_date,
                "date_iso": iso_date,
                "body_text": text_body,
                "body_html": html_body,
                "attachments": [
                    {
                        "filename": item["filename"],
                        "content_type": item["content_type"],
                        "size_bytes": item["size_bytes"],
                    }
                    for item in attachments
                ],
            }

    def manage_attachments(
        self,
        action: Literal["list", "save"],
        folder: str,
        uid: str,
        output_dir: str | None,
    ) -> dict[str, Any]:
        with self.imap_session() as imap:
            status, data = imap.select(folder, readonly=True)
            self._ensure_ok(status, data, f"Unable to select folder '{folder}'")

            status, data = imap.uid("FETCH", uid, "(RFC822)")
            self._ensure_ok(status, data, f"Unable to fetch email UID {uid}")

            message = message_from_bytes(self._extract_message_bytes(data))
            attachments = self._extract_attachments(message)

            if action == "list":
                return {
                    "ok": True,
                    "uid": uid,
                    "folder": folder,
                    "attachments": [
                        {
                            "filename": item["filename"],
                            "content_type": item["content_type"],
                            "size_bytes": item["size_bytes"],
                        }
                        for item in attachments
                    ],
                }

            if action == "save":
                base_path = Path(output_dir or f"downloads/{uid}")
                base_path.mkdir(parents=True, exist_ok=True)

                saved_files: list[str] = []
                for attachment in attachments:
                    filename = _sanitize_filename(attachment["filename"])
                    target = base_path / filename
                    target.write_bytes(attachment["payload"])
                    saved_files.append(str(target.resolve()))

                return {
                    "ok": True,
                    "uid": uid,
                    "folder": folder,
                    "saved_count": len(saved_files),
                    "saved_files": saved_files,
                }

            raise ICloudMailError(f"Unsupported action: {action}")

    def send_email(
        self,
        to: list[str],
        subject: str,
        text_body: str | None,
        html_body: str | None,
        cc: list[str] | None,
        bcc: list[str] | None,
        attachments: list[str] | None,
    ) -> dict[str, Any]:
        msg = EmailMessage()
        msg["From"] = self.config.email_address
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        plain_text = text_body or " "
        msg.set_content(plain_text)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        attachment_paths = attachments or []
        for attachment_path in attachment_paths:
            path = Path(attachment_path)
            if not path.exists() or not path.is_file():
                raise ICloudMailError(f"Attachment file not found: {attachment_path}")

            mime_type, _ = mimetypes.guess_type(path.name)
            maintype, subtype = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))
            msg.add_attachment(
                path.read_bytes(),
                maintype=maintype,
                subtype=subtype,
                filename=path.name,
            )

        recipients = list(to)
        if cc:
            recipients.extend(cc)
        if bcc:
            recipients.extend(bcc)

        with self.smtp_session() as smtp:
            smtp.send_message(msg, from_addr=self.config.email_address, to_addrs=recipients)

        return {
            "ok": True,
            "message": "Email sent successfully",
            "to": to,
            "cc": cc or [],
            "bcc_count": len(bcc or []),
            "attachments_count": len(attachment_paths),
            "subject": subject,
        }

    def organize_email(
        self,
        action: Literal["move", "mark_read", "mark_unread"],
        uid: str,
        source_folder: str,
        target_folder: str | None,
    ) -> dict[str, Any]:
        with self.imap_session() as imap:
            status, data = imap.select(source_folder)
            self._ensure_ok(status, data, f"Unable to select folder '{source_folder}'")

            if action == "move":
                if not target_folder:
                    raise ICloudMailError("target_folder is required when action is 'move'.")

                copy_status, copy_data = imap.uid("COPY", uid, target_folder)
                self._ensure_ok(copy_status, copy_data, f"Unable to move UID {uid} to '{target_folder}'")
                store_status, store_data = imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                self._ensure_ok(store_status, store_data, f"Unable to mark UID {uid} as deleted")
                expunge_status, expunge_data = imap.expunge()
                self._ensure_ok(expunge_status, expunge_data, "Unable to expunge mailbox")

                return {
                    "ok": True,
                    "message": f"Email UID {uid} moved to {target_folder}",
                    "uid": uid,
                    "source_folder": source_folder,
                    "target_folder": target_folder,
                }

            if action == "mark_read":
                mark_status, mark_data = imap.uid("STORE", uid, "+FLAGS", "(\\Seen)")
                self._ensure_ok(mark_status, mark_data, f"Unable to mark UID {uid} as read")
                return {"ok": True, "message": f"Email UID {uid} marked as read", "uid": uid}

            if action == "mark_unread":
                mark_status, mark_data = imap.uid("STORE", uid, "-FLAGS", "(\\Seen)")
                self._ensure_ok(mark_status, mark_data, f"Unable to mark UID {uid} as unread")
                return {"ok": True, "message": f"Email UID {uid} marked as unread", "uid": uid}

            raise ICloudMailError(f"Unsupported action: {action}")

    def suggest_organization(self, folder: str, sample_size: int) -> dict[str, Any]:
        with self.imap_session() as imap:
            status, data = imap.select(folder, readonly=True)
            self._ensure_ok(status, data, f"Unable to select folder '{folder}'")

            status, data = imap.uid("SEARCH", None, "ALL")
            self._ensure_ok(status, data, "Unable to fetch messages for organization suggestions")

            all_uids = data[0].decode().split() if data and data[0] else []
            selected_uids = list(reversed(all_uids))[: max(sample_size, 1)]

            sender_counter: Counter[str] = Counter()
            domain_counter: Counter[str] = Counter()
            theme_counter: Counter[str] = Counter()

            for uid in selected_uids:
                fetch_status, fetch_data = imap.uid(
                    "FETCH",
                    uid,
                    "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])",
                )
                if fetch_status != "OK" or not fetch_data:
                    continue

                try:
                    header_bytes = self._extract_message_bytes(fetch_data)
                    message = message_from_bytes(header_bytes)
                    from_value = _decode_header(message.get("From")).lower()
                    subject = _decode_header(message.get("Subject")).lower()
                except Exception:
                    continue

                sender_counter[from_value] += 1

                email_match = re.search(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", from_value)
                if email_match:
                    domain_counter[email_match.group(1).lower()] += 1

                for theme in self._infer_private_themes(subject):
                    theme_counter[theme] += 1

            top_senders = [
                {"sender": sender, "count": count}
                for sender, count in sender_counter.most_common(10)
            ]
            top_domains = [
                {"domain": domain, "count": count}
                for domain, count in domain_counter.most_common(10)
            ]
            top_themes = [
                {"theme": theme, "count": count}
                for theme, count in theme_counter.most_common(10)
            ]

            folder_suggestions = self._build_folder_suggestions(top_domains, top_themes)

            return {
                "ok": True,
                "account_mode": self.config.account_mode,
                "folder": folder,
                "sampled_emails": len(selected_uids),
                "top_senders": top_senders,
                "top_domains": top_domains,
                "top_themes": top_themes,
                "suggested_structure": folder_suggestions,
            }

    def _infer_private_themes(self, subject: str) -> list[str]:
        subject_lower = subject.lower()
        themes: list[str] = []

        mapping = {
            "Finance": ["invoice", "bank", "payment", "tax", "receipt", "bill"],
            "Travel": ["booking", "flight", "hotel", "trip", "airbnb"],
            "Shopping": ["order", "delivery", "shipment", "amazon", "store"],
            "Social": ["friend", "party", "event", "invite", "family"],
            "Subscriptions": ["newsletter", "subscription", "digest", "update"],
        }

        for theme, keywords in mapping.items():
            if any(keyword in subject_lower for keyword in keywords):
                themes.append(theme)

        if not themes:
            themes.append("General")

        return themes

    def _build_folder_suggestions(
        self,
        top_domains: list[dict[str, Any]],
        top_themes: list[dict[str, Any]],
    ) -> list[str]:
        mode = self.config.account_mode

        business_roots = ["Business/Clients", "Business/Invoices", "Business/Contracts", "Business/Vendors"]
        private_roots = ["Personal/Finance", "Personal/Travel", "Personal/Shopping", "Personal/Social", "Personal/Subscriptions"]

        if mode == "BUSINESS":
            client_folders = [f"Business/Clients/{entry['domain']}" for entry in top_domains[:5]]
            return business_roots + client_folders

        if mode == "PRIVATE":
            theme_folders = [f"Personal/{entry['theme']}" for entry in top_themes[:5]]
            return sorted(set(private_roots + theme_folders))

        mixed_business = [f"Business/Clients/{entry['domain']}" for entry in top_domains[:3]]
        mixed_private = [f"Personal/{entry['theme']}" for entry in top_themes[:3]]
        return business_roots + private_roots + mixed_business + mixed_private


def _load_config() -> MailConfig:
    load_dotenv()

    email_address = os.getenv("ICLOUD_EMAIL", "").strip()
    app_password = os.getenv("ICLOUD_APP_PASSWORD", "").strip()
    account_mode = os.getenv("ACCOUNT_MODE", "PRIVATE").strip().upper()

    missing: list[str] = []
    if not email_address:
        missing.append("ICLOUD_EMAIL")
    if not app_password:
        missing.append("ICLOUD_APP_PASSWORD")

    if missing:
        raise ICloudMailError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    if account_mode not in {"PRIVATE", "BUSINESS", "MIXED"}:
        raise ICloudMailError(
            "ACCOUNT_MODE must be one of PRIVATE, BUSINESS, or MIXED"
        )

    return MailConfig(
        email_address=email_address,
        app_password=app_password,
        account_mode=account_mode,
    )


mcp = FastMCP("icloud-mail-manager")

_CLIENT: ICloudMailClient | None = None
_CONFIG_ERROR: str | None = None

try:
    _CLIENT = ICloudMailClient(_load_config())
except Exception as exc:
    _CONFIG_ERROR = str(exc)


def _client() -> ICloudMailClient:
    if _CONFIG_ERROR:
        raise ICloudMailError(
            "Server configuration error. Verify your .env file. "
            f"Details: {_CONFIG_ERROR}"
        )
    if _CLIENT is None:
        raise ICloudMailError("Mail client is not initialized.")
    return _CLIENT


@mcp.tool()
def list_folders() -> dict[str, Any]:
    """List all folders and the complete recursive folder tree."""
    return _client().list_folders()


@mcp.tool()
def manage_folder(
    action: Literal["create", "rename", "delete"],
    folder_name: str,
    new_name: str | None = None,
) -> dict[str, Any]:
    """Create, rename, or delete folders and subfolders."""
    return _client().manage_folder(action=action, folder_name=folder_name, new_name=new_name)


@mcp.tool()
def search_emails(
    folder: str = "INBOX",
    from_address: str | None = None,
    subject: str | None = None,
    since: str | None = None,
    before: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Advanced search by sender, subject, date window, and keyword."""
    return _client().search_emails(
        folder=folder,
        from_address=from_address,
        subject=subject,
        since=since,
        before=before,
        keyword=keyword,
        limit=limit,
    )


@mcp.tool()
def read_email(uid: str, folder: str = "INBOX") -> dict[str, Any]:
    """Read a full email by UID including plain text, HTML body, and attachment metadata."""
    return _client().read_email(folder=folder, uid=uid)


@mcp.tool()
def manage_attachments(
    action: Literal["list", "save"],
    uid: str,
    folder: str = "INBOX",
    output_dir: str | None = None,
) -> dict[str, Any]:
    """List or save attachments for a specific email UID."""
    return _client().manage_attachments(action=action, folder=folder, uid=uid, output_dir=output_dir)


@mcp.tool()
def send_email(
    to: list[str],
    subject: str,
    text_body: str | None = None,
    html_body: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    """Send an email with rich text and optional attachments."""
    return _client().send_email(
        to=to,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
    )


@mcp.tool()
def organize_email(
    action: Literal["move", "mark_read", "mark_unread"],
    uid: str,
    source_folder: str = "INBOX",
    target_folder: str | None = None,
) -> dict[str, Any]:
    """Move email to a folder or update read/unread state."""
    return _client().organize_email(
        action=action,
        uid=uid,
        source_folder=source_folder,
        target_folder=target_folder,
    )


@mcp.tool()
def suggest_organization(folder: str = "INBOX", sample_size: int = 200) -> dict[str, Any]:
    """Analyze frequent senders and suggest folder strategies based on ACCOUNT_MODE."""
    return _client().suggest_organization(folder=folder, sample_size=sample_size)


if __name__ == "__main__":
    mcp.run()
