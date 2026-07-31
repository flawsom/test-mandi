#!/usr/bin/env python3
"""
Apply the MandiIQ glassmorphism design system to any markdown file:
- Cinematic gradient header bar
- Glassmorphism cards wrapping each section (## heading)
- SVG wave dividers between sections
- All original content preserved verbatim inside the cards

Usage:
    python scripts/apply_glassmorphism.py <file.md> [file2.md ...]
    python scripts/apply_glassmorphism.py --all
"""

import sys
import os
import re


def svg_divider(index):
    """Generate an SVG wave divider with a unique gradient ID per instance."""
    gid = f"wg-{index}"
    return f"""<br />
<div style="position:relative; height:60px; overflow:hidden; width:100%; margin:8px 0;">
  <svg viewBox="0 0 1440 60" width="100%" height="60" preserveAspectRatio="none" style="position:absolute;bottom:0;">
    <defs>
      <linearGradient id="{gid}" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#0B0F1E" stop-opacity="0" />
        <stop offset="25%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="50%" stop-color="#00FF88" stop-opacity="0.4" />
        <stop offset="75%" stop-color="#00FF88" stop-opacity="0.25" />
        <stop offset="100%" stop-color="#0B0F1E" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path d="M0,30 C240,10 480,50 720,30 C960,10 1200,50 1440,30 L1440,60 L0,60 Z" fill="url(#{gid})" opacity="0.6" />
    <path d="M0,40 C240,25 480,55 720,40 C960,25 1200,55 1440,40 L1440,60 L0,60 Z" fill="url(#{gid})" opacity="0.3" />
  </svg>
</div>
<br />"""

GLASS_OPEN = """<div style="background:linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px 28px; margin:16px 0; box-shadow:0 8px 32px rgba(0,0,0,0.4); position:relative; overflow:hidden;">
<div style="position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, transparent, #00FF88, transparent); opacity:0.6;"></div>
<div style="position:absolute; top:-60px; right:-60px; width:120px; height:120px; background:radial-gradient(circle, rgba(0,255,136,0.15) 0%, transparent 70%);"></div>"""

GLASS_CLOSE = "</div></div></div>"

# Generic SVG icon set keyed by keyword (small heroicons-style icons)
ICON_ROCKET = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/></svg>'
ICON_CHART = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><rect x="3" y="12" width="4" height="9"/><rect x="10" y="7" width="4" height="14"/><rect x="17" y="3" width="4" height="18"/></svg>'
ICON_DATABASE = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>'
ICON_SHIELD = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
ICON_TUBE = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M14 2H10"/><path d="M12 2v10"/><path d="M9 10a4 4 0 0 0 6 0"/><path d="M14 6a4 4 0 0 1 0-4"/><path d="M6 18a4 4 0 0 0 4 4h4a4 4 0 0 0 4-4"/></svg>'
ICON_HANDSHAKE = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M20.42 4.58a5.4 5.4 0 0 0-7.65 0l-.77.78-.77-.78a5.4 5.4 0 0 0-7.65 0C1.46 6.7 1.33 10.28 4 13l8 8 8-8c2.67-2.72 2.54-6.3.42-8.42z"/></svg>'
ICON_QUESTION = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
ICON_LIGHT = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/></svg>'
ICON_DOC = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
ICON_MAP = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'
ICON_HEART = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="#FF4B4B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>'
ICON_TAG = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>'
ICON_FOLDER = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
ICON_KEY = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.78 7.78 5.5 5.5 0 0 1 7.78-7.78zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>'
ICON_CLOCK = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
ICON_FLAG = '<svg xmlns="http://www.w3.org/2000/svg" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>'

def pick_icon(heading):
    """Pick an icon based on heading keywords."""
    h = heading.lower()
    if any(k in h for k in ["deploy", "release", "server", "production", "pipeline", "build"]):
        return ICON_ROCKET
    if any(k in h for k in ["architect", "system", "design", "overview", "diagram", "workflow"]):
        return ICON_MAP
    if any(k in h for k in ["data", "database", "duckdb", "warehouse", "storage", "schema"]):
        return ICON_DATABASE
    if any(k in h for k in ["api", "endpoint", "curl", "rest", "request"]):
        return ICON_TAG
    if any(k in h for k in ["test", "qa", "quality", "verify", "verification", "check"]):
        return ICON_TUBE
    if any(k in h for k in ["metric", "grafana", "monitor", "observability", "health", "status", "kpi"]):
        return ICON_CHART
    if any(k in h for k in ["security"]):
        return ICON_SHIELD
    if any(k in h for k in ["auth", "key", "secret", "token", "env"]):
        return ICON_KEY
    if any(k in h for k in ["faq", "question", "troubleshoot", "common issue"]):
        return ICON_QUESTION
    if any(k in h for k in ["contribut", "community", "code of conduct", "license", "support"]):
        return ICON_HANDSHAKE
    if any(k in h for k in ["credits", "acknowledge", "thanks"]):
        return ICON_HEART
    if any(k in h for k in ["roadmap", "timeline", "history", "changelog", "log"]):
        return ICON_CLOCK
    if any(k in h for k in ["quick start", "getting started", "install", "setup", "usage", "guide"]):
        return ICON_FLAG
    if any(k in h for k in ["structure", "tree", "file", "layout", "folder", "repo"]):
        return ICON_FOLDER
    if any(k in h for k in ["background", "motivation", "problem", "finding", "result", "insight"]):
        return ICON_LIGHT
    return ICON_DOC

def slugify_heading(text):
    """Convert heading text to a GitHub-compatible anchor slug.
    Matches GitHub's algorithm: lowercase, keep [a-z0-9-_], spaces -> hyphens.
    """
    import re as _re
    s = text.lower().strip()
    s = _re.sub(r'[^a-z0-9\s_-]', '', s)
    s = _re.sub(r'\s+', '-', s)
    s = _re.sub(r'-+', '-', s).strip('-')
    return s or 'section'


def make_header(title, subtitle=""):
    """Build the cinematic header bar."""
    safe_title = title.replace("_", " ").replace("-", " ").title()
    if safe_title.lower().endswith(".md"):
        safe_title = safe_title[:-3]
    sub = f"<h4 style=\"color:#94A3B8; font-weight:400; font-size:0.95em; margin:6px 0 0 0;\">{subtitle}</h4>" if subtitle else ""
    return f'''<div align="center" style="position:relative; overflow:hidden; border-radius:20px; background:linear-gradient(135deg, #0B0F1E 0%, #0F1F15 40%, #0B0F1E 100%); padding:44px 20px 36px; margin-bottom:8px; border:1px solid rgba(0,255,136,0.08);">

<div style="position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:600px; height:300px; background:radial-gradient(ellipse, rgba(0,255,136,0.12) 0%, transparent 70%); pointer-events:none;"></div>
<div style="position:absolute; top:0; left:10%; right:10%; height:1px; background:linear-gradient(90deg, transparent, rgba(0,255,136,0.5), transparent);"></div>

<div style="position:relative; z-index:1;">
<h1 style="margin:0; font-size:2.2em; font-weight:700; color:#E0E0E0; letter-spacing:-0.5px;">
  <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#00FF88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M12 2v18"/><path d="M8 6c0-2 4-4 4 0"/><path d="M16 6c0-2-4-4-4 0"/><path d="M8 12c0-2 4-4 4 0"/><path d="M16 12c0-2-4-4-4 0"/><path d="M6 18c0-3 6-5 6 0"/><path d="M18 18c0-3-6-5-6 0"/><path d="M9 22h6"/></svg>
  {safe_title}
</h1>
{sub}
</div>

</div>'''

def transform_markdown(content, filename):
    """Transform markdown content into glassmorphism design."""
    lines = content.split("\n")

    # Extract the first H1 as the title, remove it from body
    title = os.path.splitext(os.path.basename(filename))[0]
    body_lines = []
    for i, line in enumerate(lines):
        if line.startswith("# ") and i < 10:
            title = line[2:].strip()
            continue
        body_lines.append(line)

    # Find section boundaries (## headings) outside code blocks
    sections = []  # list of (heading_text, [content_lines])
    in_code = False
    current_heading = None
    current_lines = []

    for line in body_lines:
        stripped = line.strip()

        # Toggle code blocks
        if stripped.startswith("```"):
            in_code = not in_code
            current_lines.append(line)
            continue

        # Detect new section (## heading outside code)
        if not in_code and stripped.startswith("## "):
            # Save current section
            if current_heading is not None or current_lines:
                sections.append((current_heading, current_lines))
            current_heading = stripped[3:].strip()
            current_lines = []
            continue

        # Detect H2 followed by content (e.g. "## Title" variants)
        current_lines.append(line)

    # Save last section
    if current_heading is not None or current_lines:
        sections.append((current_heading, current_lines))

    # Filter out sections with no content
    sections = [(h, ln) for h, ln in sections if any(l.strip() for l in ln)]

    # Build output
    out = []
    out.append(make_header(title, "MandiIQ Documentation"))

    # Track used slugs to avoid duplicate anchors across the document
    seen_slugs = {}

    def _unique_slug(text):
        slug = slugify_heading(text)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            return f"{slug}-{seen_slugs[slug]}"
        seen_slugs[slug] = 0
        return slug

    for idx, (heading, sec_lines) in enumerate(sections):
        # Section heading rendered as glass-styled h2 with anchor (or plain if no heading)
        if heading:
            icon = pick_icon(heading)
            slug = _unique_slug(heading)
            heading_html = f'''<a name="{slug}"></a>
<h2 style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif; font-size:1.5em; font-weight:600; color:#E0E0E0; display:flex; align-items:center; gap:10px; margin:0 0 16px 0; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.06);">
  {icon} {heading}
</h2>'''
            section_body = heading_html + "\n\n" + "\n".join(sec_lines)
        else:
            section_body = "\n\n".join(sec_lines)

        out.append(GLASS_OPEN)
        out.append(section_body)
        out.append(GLASS_CLOSE)

        # SVG divider between sections (not after the last) - unique gradient ID
        if idx < len(sections) - 1:
            out.append(svg_divider(idx))

    # Back to top
    out.append('''
<div align="center">
<br />
<a href="#" style="display:inline-block; padding:8px 20px; border-radius:10px; background:linear-gradient(135deg, rgba(0,255,136,0.12) 0%, rgba(0,255,136,0.04) 100%); border:1px solid rgba(0,255,136,0.2); color:#00FF88; font-weight:500; text-decoration:none; font-size:14px;">&#x2191; Back to Top</a>
<br /><br />
</div>''')

    return "\n".join(out)


def validate_balanced_code_fences(content):
    """Ensure code fences are balanced."""
    count = content.count("```")
    return count % 2 == 0


def main():
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    targets = []
    if "--all" in args:
        # All project markdown docs (excluding README which is already done)
        exclude = {"README.md", "repomix-codebase.md", "repomix-new.md", "repomix-output.md"}
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", ".freebuff", "archive", "__pycache__", ".pytest_cache", "memory", "frontend", ".github")]
            for f in files:
                if f.endswith(".md") and f not in exclude:
                    path = os.path.join(root, f)
                    if "node_modules" not in path and ".pytest_cache" not in path:
                        targets.append(path)
        targets.sort()
    else:
        targets = [a for a in args if a != "--all"]

    for path in targets:
        if not os.path.exists(path):
            print(f"SKIP (not found): {path}")
            continue

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Skip if already transformed
        if 'border-radius:16px' in content:
            print(f"SKIP (already transformed): {path}")
            continue

        new_content = transform_markdown(content, path)

        # Validate
        if not validate_balanced_code_fences(new_content):
            print(f"WARN (unbalanced code fences): {path}")

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"OK: {path} ({len(content.splitlines())} -> {len(new_content.splitlines())} lines)")


if __name__ == "__main__":
    main()
