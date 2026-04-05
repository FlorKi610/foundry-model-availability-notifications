#!/usr/bin/env python3
"""Send a rich Teams Adaptive Card and/or HTML email for model availability changes."""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path
from datetime import datetime, timezone


# ── Helpers ─────────────────────────────────────────────────────────
EMEA_REGIONS = [
    "Finland Central", "France Central", "Germany West Central",
    "Italy North", "Norway East", "Poland Central", "South Africa North",
    "Spain Central", "Sweden Central", "Switzerland North",
    "Switzerland West", "UAE North", "UK South", "West Europe",
]

SKU_ICONS = {
    "datazone": "📊", "global-batch": "🔄", "global": "🌐", "regional": "🏢",
}

IMPACT_ICONS = {
    "retired": "⛔", "new": "🆕", "expanded": "📈", "mixed": "🔀", "reduced": "📉",
}


def sku_category(sku: str) -> tuple[str, str]:
    if sku.startswith("global-batch"):  return "🔄", "Batch"
    if sku.startswith("datazone"):      return "📊", "Datazone"
    if "global" in sku:                 return "🌐", "Global"
    return "🏢", "Regional"


def human_date(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:16]
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return f"{months[d.month-1]} {d.day}, {d.year} at {d.strftime('%H:%M')} UTC"


def has_changes(diff: dict) -> bool:
    for ch in (diff.get("changes") or {}).values():
        a = ch.get("all") or {}
        if a.get("added") or a.get("removed") or ch.get("model_removed"):
            return True
        for s in (ch.get("skus") or {}).values():
            if s.get("added") or s.get("removed") or s.get("sku_removed"):
                return True
    return False


def classify_models(diff: dict, europe: dict) -> list[dict]:
    """Classify each changed model with impact type."""
    eu_by_model = {m["model"]: m for m in (europe.get("views") or {}).get("by_model", [])}
    results = []
    for model, ch in sorted((diff.get("changes") or {}).items()):
        has_a = bool((ch.get("all") or {}).get("added"))
        has_r = bool((ch.get("all") or {}).get("removed"))
        for s in (ch.get("skus") or {}).values():
            if s.get("added"): has_a = True
            if s.get("removed") or s.get("sku_removed"): has_r = True
        if not has_a and not has_r and not ch.get("model_removed"):
            continue

        if ch.get("model_removed"):     impact = "retired"
        elif has_a and has_r:           impact = "mixed"
        elif has_a:                     impact = "expanded"
        elif has_r:                     impact = "reduced"
        else:                           impact = "changed"

        eu = eu_by_model.get(model, {})
        eu_added = len((eu.get("updates") or {}).get("added_regions", []))
        if impact == "expanded" and eu.get("region_count", 0) > 0 and eu_added == eu.get("region_count"):
            impact = "new"

        results.append({
            "model": model,
            "impact": impact,
            "icon": IMPACT_ICONS.get(impact, "ℹ️"),
            "eu_regions": eu.get("region_count", 0),
            "eu_added": (eu.get("updates") or {}).get("added_regions", []),
            "eu_removed": (eu.get("updates") or {}).get("removed_regions", []),
            "skus": eu.get("skus", []),
        })
    return results


def build_datazone_matrix(snapshot: dict) -> list[dict]:
    """Build a Datazone availability matrix for EMEA regions."""
    rows = []
    for model_name in sorted(snapshot.keys()):
        md = snapshot[model_name]
        skus = md.get("skus", {})
        dz_skus = {k: v for k, v in skus.items() if "datazone" in k.lower()}
        if not dz_skus:
            continue
        for sku_key, sku_info in sorted(dz_skus.items()):
            regions = sku_info.get("regions", [])
            emea_present = [r for r in EMEA_REGIONS if r in regions]
            if not emea_present:
                continue
            rows.append({
                "model": model_name,
                "sku_label": sku_info.get("label", sku_key),
                "regions": {r: (r in regions) for r in EMEA_REGIONS},
                "total": len(regions),
            })
    return rows


# ── Teams Adaptive Card ────────────────────────────────────────────
def build_teams_card(diff: dict, europe: dict, snapshot: dict, issue_url: str = "") -> dict:
    """Build a Teams Adaptive Card payload."""
    timestamp = diff.get("timestamp", datetime.now(timezone.utc).isoformat())
    models = classify_models(diff, europe)

    # Summary stats
    eu_stats = europe.get("stats", {})
    eu_added = sum(len(m["eu_added"]) for m in models)
    eu_removed = sum(len(m["eu_removed"]) for m in models)

    # At-a-glance rows
    glance_rows = []
    for m in models[:15]:  # Limit for card size
        skus_str = ", ".join(set(sku_category(s["sku"])[1] for s in m["skus"])) or "—"
        delta = ""
        if m["eu_added"]: delta += f" +{len(m['eu_added'])}"
        if m["eu_removed"]: delta += f" -{len(m['eu_removed'])}"
        glance_rows.append({
            "type": "TableRow",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": f"{m['icon']}", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": m["model"], "weight": "Bolder", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": f"{m['eu_regions']}{delta}", "wrap": True}]},
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": skus_str, "wrap": True}]},
            ],
        })

    # Datazone EMEA matrix (compact: top regions only)
    dz_matrix = build_datazone_matrix(snapshot)
    emea_short = ["FR", "DE", "IT", "NO", "PL", "ES", "SE", "CH", "UK", "WEU"]
    emea_map = {
        "France Central": "FR", "Germany West Central": "DE", "Italy North": "IT",
        "Norway East": "NO", "Poland Central": "PL", "Spain Central": "ES",
        "Sweden Central": "SE", "Switzerland North": "CH", "UK South": "UK",
        "West Europe": "WEU",
    }
    dz_rows = []
    seen_models = set()
    for row in dz_matrix:
        key = row["model"]
        if key in seen_models:
            continue
        seen_models.add(key)
        # Aggregate all datazone SKUs for this model
        checks = []
        for r_full, r_short in emea_map.items():
            available = any(
                dz["regions"].get(r_full, False)
                for dz in dz_matrix if dz["model"] == key
            )
            checks.append("✅" if available else "—")
        dz_rows.append({
            "type": "TableRow",
            "cells": [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": key, "size": "Small", "wrap": True}]},
            ] + [
                {"type": "TableCell", "items": [{"type": "TextBlock", "text": c, "size": "Small", "horizontalAlignment": "Center"}]}
                for c in checks
            ],
        })

    # Build card
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.5",
                "body": [
                    # Header
                    {"type": "TextBlock", "text": "📊 Azure AI Foundry — Model Changes", "size": "Large", "weight": "Bolder", "wrap": True},
                    {"type": "TextBlock", "text": f"Scanned: {human_date(timestamp)}", "size": "Small", "isSubtle": True, "spacing": "None"},
                    # TL;DR
                    {"type": "TextBlock", "text": f"🇪🇺 Europe: **+{eu_added}** / **-{eu_removed}** placements · **{len(models)} models** changed", "wrap": True, "spacing": "Medium"},
                    # Separator
                    {"type": "TextBlock", "text": "⚡ **At a Glance**", "size": "Medium", "weight": "Bolder", "spacing": "Medium"},
                    # At-a-glance table
                    {
                        "type": "Table",
                        "columns": [
                            {"width": "40px"}, {"width": "stretch"}, {"width": "80px"}, {"width": "100px"},
                        ],
                        "firstRowAsHeader": True,
                        "rows": [{
                            "type": "TableRow", "style": "accent",
                            "cells": [
                                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "", "weight": "Bolder"}]},
                                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Model", "weight": "Bolder"}]},
                                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "EU Reg.", "weight": "Bolder"}]},
                                {"type": "TableCell", "items": [{"type": "TextBlock", "text": "SKUs", "weight": "Bolder"}]},
                            ],
                        }] + glance_rows,
                    },
                ],
                "actions": [],
            },
        }],
    }

    # Add Datazone matrix if there are entries
    if dz_rows:
        card["attachments"][0]["content"]["body"].extend([
            {"type": "TextBlock", "text": "📊 **Datazone EMEA Matrix**", "size": "Medium", "weight": "Bolder", "spacing": "Large"},
            {
                "type": "Table",
                "columns": [{"width": "stretch"}] + [{"width": "30px"} for _ in emea_short],
                "firstRowAsHeader": True,
                "rows": [{
                    "type": "TableRow", "style": "accent",
                    "cells": [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": "Model", "weight": "Bolder", "size": "Small"}]},
                    ] + [
                        {"type": "TableCell", "items": [{"type": "TextBlock", "text": r, "weight": "Bolder", "size": "Small", "horizontalAlignment": "Center"}]}
                        for r in emea_short
                    ],
                }] + dz_rows[:20],  # Limit rows for card size
            },
        ])

    # Action buttons
    if issue_url:
        card["attachments"][0]["content"]["actions"].append({
            "type": "Action.OpenUrl", "title": "📋 Full Report on GitHub", "url": issue_url,
        })

    return card


# ── HTML Email ──────────────────────────────────────────────────────
def build_html_email(diff: dict, europe: dict, snapshot: dict, dashboard_url: str = "", issue_url: str = "") -> str:
    """Build an HTML email body."""
    timestamp = diff.get("timestamp", "")
    models = classify_models(diff, europe)
    eu_added = sum(len(m["eu_added"]) for m in models)
    eu_removed = sum(len(m["eu_removed"]) for m in models)

    # At-a-glance rows
    glance_html = ""
    for m in models:
        skus_str = ", ".join(set(sku_category(s["sku"])[1] for s in m["skus"])) or "—"
        delta = ""
        if m["eu_added"]: delta += f' <span style="color:#22863a">+{len(m["eu_added"])}</span>'
        if m["eu_removed"]: delta += f' <span style="color:#cb2431">-{len(m["eu_removed"])}</span>'
        glance_html += f"""<tr>
          <td style="padding:4px 8px;text-align:center">{m['icon']}</td>
          <td style="padding:4px 8px"><b>{m['model']}</b></td>
          <td style="padding:4px 8px;text-align:center">{m['eu_regions']}{delta}</td>
          <td style="padding:4px 8px">{skus_str}</td>
        </tr>"""

    # Datazone matrix
    dz_matrix = build_datazone_matrix(snapshot)
    emea_map = {
        "France Central": "FR", "Germany West Central": "DE", "Italy North": "IT",
        "Norway East": "NO", "Poland Central": "PL", "Spain Central": "ES",
        "Sweden Central": "SE", "Switzerland North": "CH", "UK South": "UK",
        "West Europe": "WEU",
    }
    dz_html = ""
    seen = set()
    for row in dz_matrix:
        if row["model"] in seen:
            continue
        seen.add(row["model"])
        cells = ""
        for r_full in emea_map:
            avail = any(dz["regions"].get(r_full, False) for dz in dz_matrix if dz["model"] == row["model"])
            cells += f'<td style="padding:2px 4px;text-align:center">{"✅" if avail else "—"}</td>'
        dz_html += f'<tr><td style="padding:2px 6px"><b>{row["model"]}</b></td>{cells}</tr>'

    dz_header = "".join(f'<th style="padding:2px 4px;font-size:11px">{v}</th>' for v in emea_map.values())

    links = ""
    if issue_url:
        links += f'<a href="{issue_url}">📋 Full Report</a> · '
    if dashboard_url:
        links += f'<a href="{dashboard_url}">📖 Dashboard</a>'

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Segoe UI,Helvetica,Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#24292e">

<h1 style="border-bottom:2px solid #0078d4;padding-bottom:8px">📊 Azure AI Foundry — Model Changes</h1>
<p style="color:#586069">Scanned: {human_date(timestamp)}</p>

<div style="background:#f1f8ff;border-left:4px solid #0366d6;padding:12px 16px;margin:16px 0">
  <b>🇪🇺 Europe:</b> +{eu_added} / -{eu_removed} placements · <b>{len(models)} models</b> changed
</div>

<h2>⚡ At a Glance</h2>
<table style="border-collapse:collapse;width:100%">
  <tr style="background:#f6f8fa;border-bottom:2px solid #e1e4e8">
    <th style="padding:6px 8px;text-align:center;width:40px"></th>
    <th style="padding:6px 8px;text-align:left">Model</th>
    <th style="padding:6px 8px;text-align:center">EU Regions</th>
    <th style="padding:6px 8px;text-align:left">SKUs</th>
  </tr>
  {glance_html}
</table>

<h2 style="margin-top:24px">📊 Datazone EMEA Matrix</h2>
<table style="border-collapse:collapse;width:100%;font-size:12px">
  <tr style="background:#f6f8fa;border-bottom:2px solid #e1e4e8">
    <th style="padding:4px 6px;text-align:left">Model</th>
    {dz_header}
  </tr>
  {dz_html}
</table>

<hr style="margin-top:24px;border:none;border-top:1px solid #e1e4e8">
<p style="color:#586069;font-size:13px">{links}</p>

</body></html>"""
    return html


def build_subject(diff: dict, models: list[dict]) -> str:
    timestamp = diff.get("timestamp", "")[:10]
    eu_added = sum(len(m["eu_added"]) for m in models)
    eu_removed = sum(len(m["eu_removed"]) for m in models)
    return f"📊 Model Watch | {timestamp} | +{eu_added}/-{eu_removed} EU | {len(models)} models changed"


# ── Send functions ──────────────────────────────────────────────────
def send_teams(webhook_url: str, card: dict) -> None:
    import requests
    resp = requests.post(webhook_url, json=card, timeout=30)
    resp.raise_for_status()
    print(f"Teams card sent (status {resp.status_code})")


def send_email_html(subject: str, html_body: str, text_fallback: str = "") -> None:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    email_from = os.getenv("EMAIL_FROM", "").strip()
    email_to = [e.strip() for e in os.getenv("EMAIL_TO", "").split(",") if e.strip()]

    missing = [n for n, v in {"SMTP_HOST": smtp_host, "SMTP_USERNAME": smtp_user,
               "SMTP_PASSWORD": smtp_pass, "EMAIL_FROM": email_from, "EMAIL_TO": ",".join(email_to)}.items() if not v]
    if missing:
        raise RuntimeError(f"Missing email config: {', '.join(missing)}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    msg.set_content(text_fallback or "See HTML version of this email.")
    msg.add_alternative(html_body, subtype="html")

    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() != "false"
    if use_tls:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as s:
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
    print(f"HTML email sent to {', '.join(email_to)}")


# ── Main ────────────────────────────────────────────────────────────
def main() -> int:
    diff_path = Path("region_diff.json")
    europe_path = Path("region_diff_europe.json")
    snapshot_path = Path(".region-watch/regions_snapshot.json")

    if not diff_path.exists():
        print("region_diff.json not found, skipping notifications")
        return 0

    diff = json.loads(diff_path.read_text("utf-8"))
    if not has_changes(diff):
        print("No changes detected, skipping notifications")
        return 0

    europe = json.loads(europe_path.read_text("utf-8")) if europe_path.exists() else {}
    snapshot = json.loads(snapshot_path.read_text("utf-8")) if snapshot_path.exists() else {}

    models = classify_models(diff, europe)
    issue_url = os.getenv("ISSUE_URL", "")
    dashboard_url = os.getenv("DASHBOARD_URL", "")
    if not dashboard_url:
        repo = os.getenv("GITHUB_REPOSITORY", "")
        if repo:
            owner = repo.split("/")[0]
            dashboard_url = f"https://{owner}.github.io/{repo.split('/')[-1]}/"

    # Teams
    webhook = os.getenv("TEAMS_WEBHOOK", "").strip()
    if webhook:
        try:
            card = build_teams_card(diff, europe, snapshot, issue_url)
            send_teams(webhook, card)
        except Exception as e:
            print(f"Teams notification failed: {e}", file=sys.stderr)

    # Email
    if os.getenv("SMTP_HOST", "").strip():
        try:
            subject = build_subject(diff, models)
            html = build_html_email(diff, europe, snapshot, dashboard_url, issue_url)
            send_email_html(subject, html)
        except Exception as e:
            print(f"Email notification failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
