#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def has_changes(diff_payload: dict) -> bool:
    for change in (diff_payload.get("changes") or {}).values():
        all_change = change.get("all") or {}
        if all_change.get("added") or all_change.get("removed") or change.get("model_removed"):
            return True
        for sku_change in (change.get("skus") or {}).values():
            if sku_change.get("added") or sku_change.get("removed") or sku_change.get("sku_removed"):
                return True
    return False


def get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def format_region_list(regions: list[str]) -> str:
    return ", ".join(regions) if regions else "-"


def build_subject(diff_payload: dict) -> str:
    changed_models = len(diff_payload.get("changes") or {})
    timestamp = diff_payload.get("timestamp", "unknown time")
    return f"[Azure Model Watch] {changed_models} changed model(s) at {timestamp}"


def build_text_body(diff_payload: dict, dashboard_url: str) -> str:
    lines: list[str] = []
    timestamp = diff_payload.get("timestamp", "unknown time")
    changes = diff_payload.get("changes") or {}

    lines.append("Azure AI model region diff detected")
    lines.append("")
    lines.append(f"Timestamp: {timestamp}")
    lines.append(f"Changed models: {len(changes)}")
    lines.append("")

    for model_name, change in sorted(changes.items()):
        lines.append(model_name)
        lines.append("-" * len(model_name))

        overall = change.get("all") or {}
        if overall.get("added"):
            lines.append(f"Added regions: {format_region_list(sorted(overall['added']))}")
        if overall.get("removed"):
            lines.append(f"Removed regions: {format_region_list(sorted(overall['removed']))}")
        if change.get("model_removed"):
            lines.append("Model removed: yes")

        for sku_key, sku_change in sorted((change.get("skus") or {}).items()):
            label = sku_change.get("label") or sku_key
            if sku_change.get("added"):
                lines.append(f"SKU {label} added: {format_region_list(sorted(sku_change['added']))}")
            if sku_change.get("removed"):
                lines.append(f"SKU {label} removed: {format_region_list(sorted(sku_change['removed']))}")
            if sku_change.get("sku_removed"):
                lines.append(f"SKU {label}: removed")

        lines.append("")

    lines.append(f"Dashboard: {dashboard_url}")
    return "\n".join(lines).strip() + "\n"


def send_mail(subject: str, body: str) -> None:
    smtp_host = get_env("SMTP_HOST")
    smtp_port = int(get_env("SMTP_PORT", "587"))
    smtp_username = get_env("SMTP_USERNAME")
    smtp_password = get_env("SMTP_PASSWORD")
    email_from = get_env("EMAIL_FROM")
    email_to = [entry.strip() for entry in get_env("EMAIL_TO").split(",") if entry.strip()]
    use_tls = get_env("SMTP_USE_TLS", "true").lower() != "false"

    missing = [
        name
        for name, value in {
            "SMTP_HOST": smtp_host,
            "SMTP_USERNAME": smtp_username,
            "SMTP_PASSWORD": smtp_password,
            "EMAIL_FROM": email_from,
            "EMAIL_TO": ",".join(email_to),
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(f"Missing email configuration: {', '.join(missing)}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = ", ".join(email_to)
    message.set_content(body)

    if use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls(context=context)
            server.login(smtp_username, smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(message)


def main() -> int:
    diff_path = Path("region_diff.json")
    if not diff_path.exists():
        print("region_diff.json not found, skipping email")
        return 0

    diff_payload = json.loads(diff_path.read_text(encoding="utf-8"))
    if not has_changes(diff_payload):
        print("No changes detected, skipping email")
        return 0

    dashboard_url = get_env("DASHBOARD_URL", "")
    if not dashboard_url:
        repository = get_env("GITHUB_REPOSITORY")
        if repository:
            owner, repo = repository.split("/", 1)
            dashboard_url = f"https://{owner}.github.io/{repo}/"
        else:
            dashboard_url = "Dashboard URL not configured"

    subject = build_subject(diff_payload)
    body = build_text_body(diff_payload, dashboard_url)
    send_mail(subject, body)
    print("Diff email sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())