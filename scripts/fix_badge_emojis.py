"""DEPRECATED — do not use.

This script restores emoji characters inside shields.io badge URLs after a
CDN-img injection pass. The project now uses inline SVGs exclusively
(see scripts/convert_cdn_emojis_to_svg.py); running this would REINTRODUCE
CDN references. Kept only for reference.
"""

import re
import os
from pathlib import Path

CDN_PATTERN = re.compile(r'<img src="https://raw\.githubusercontent\.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/[^"]+" alt="" width="20" height="20" style="vertical-align:middle" />')

# Map: CDN img tag content → original emoji
# (partial match on the filename)
IMG_TO_EMOJI = {
    "Rocket.png": "\U0001F680",          # 🚀
    "Bar%20Chart.png": "\U0001F4CA",     # 📊
    "Open%20Book.png": "\U0001F4D6",     # 📖
    "High%20Voltage.png": "\u26A1",      # ⚡
    "Octopus.png": "\U0001F419",         # 🐙
    "Camera%20with%20Flash.png": "\U0001F4F7",  # 📸
    "Clapper%20Board.png": "\U0001F3AC", # 🎬
    "Robot.png": "\U0001F916",           # 🤖
    "Raising%20Hands.png": "\U0001F64C", # 🙌
    "Key.png": "\U0001F511",             # 🔑
    "Locked%20with%20Key.png": "\U0001F510", # 🔐
    "Globe%20with%20Meridians.png": "\U0001F30D", # 🌐
    "Beer%20Mug.png": "\U0001F37A",      # 🍺
    "Locked.png": "\U0001F512",          # 🔒
    "Bug.png": "\U0001F41B",             # 🐛
    "Loudspeaker.png": "\U0001F4E3",     # 📣
    "Package.png": "\U0001F4E6",         # 📦
    "Shield.png": "\U0001F6E1",          # 🛡️
    "Cross%20Mark.png": "\u274C",        # ❌
    "Check%20Mark%20Button.png": "\u2705", # ✅
    "White%20Medium%20Star.png": "\u2B50", # ⭐
    "Sparkles.png": "\U0001F31F",        # ✨
    "Sheaf%20of%20Rice.png": "\U0001F33E", # 🌾
    "Chart%20with%20Upwards%20Trend.png": "\U0001F4C8", # 📈
    "Fire.png": "\U0001F525",            # 🔥
}

def restore_emoji_in_url(url_content, line):
    """Find CDN img tags in URL contexts and restore the original emoji."""
    result = line
    for match in CDN_PATTERN.finditer(line):
        tag = match.group()
        # Find which emoji this corresponds to
        for filename, emoji in IMG_TO_EMOJI.items():
            if filename in tag:
                result = result.replace(tag, emoji, 1)
                break
    return result


def process_file(filepath):
    """Fix badges in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    fixed_lines = []
    total_fixed = 0
    
    for line in lines:
        # Only process lines that contain shields.io badge URLs
        if 'img.shields.io/badge/' in line:
            original = line
            line = restore_emoji_in_url(None, line)
            if line != original:
                total_fixed += 1
        fixed_lines.append(line)
    
    if total_fixed > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(fixed_lines))
        print(f"  OK {total_fixed} badge URLs fixed in {filepath}")
    else:
        print(f"  -- No badges to fix in {filepath}")
    
    return total_fixed


def main():
    base = Path.cwd()
    
    # Files that might have shields.io badges with emojis
    files = [
        "README.md",
        "SUPPORT.md",
        "DEPLOY.md",
        ".github/welcome-post-draft.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "mandi_rdd/README.md",
        "mandi_rdd/docs/API_KEY_SETUP.md",
        "mandi_rdd/PROJECT_STATUS.md",
    ]
    
    total = 0
    for f in files:
        path = base / f
        if path.exists():
            count = process_file(str(path))
            total += count
        else:
            print(f"  -- {f} not found")
    
    print(f"\n{'='*50}")
    print(f"Total: {total} badge URLs fixed")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
