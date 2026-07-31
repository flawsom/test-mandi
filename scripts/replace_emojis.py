"""
DEPRECATED — do not use.

This script REPLACES Unicode emojis with Animated-Fluent-Emojis CDN <img> tags.
The project has moved to inline SVGs (see scripts/convert_cdn_emojis_to_svg.py);
running this would REINTRODUCE external CDN references the repo now forbids.
Kept only for reference. Use convert_cdn_emojis_to_svg.py instead.
"""

import re
import os
import sys
from pathlib import Path

# ── CDN base URL ──
CDN_BASE = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis"

# ── Emoji mapping built from codepoints ──
# Map: codepoint hex string -> (category_folder, filename)
EMOJI_MAP = {}

def _reg(cp, cat, name):
    """Register an emoji by its hex codepoint."""
    ch = chr(int(cp, 16))
    EMOJI_MAP[ch] = (cat, name)

def _reg_range(start_cp, end_cp, cat, name_prefix):
    """Register a range of codepoints (unused but kept for future)."""
    pass

# ── Activities ──
_reg("1F31F", "Activities", "Sparkles")
_reg("26A1", "Activities", "High%20Voltage")
_reg("1F3AF", "Activities", "Direct%20Hit")
_reg("1F3AC", "Activities", "Clapper%20Board")
_reg("1F3AE", "Activities", "Video%20Game")
_reg("1F4F9", "Activities", "Video%20Camera")
_reg("1F389", "Activities", "Party%20Popper")
_reg("1F3C6", "Activities", "Trophy")
_reg("1F3AA", "Activities", "Circus%20Tent")
_reg("1F44F", "Activities", "Clapping%20Hands")
_reg("1F64C", "Activities", "Raising%20Hands")
_reg("1F64F", "Activities", "Folded%20Hands")
_reg("1F3B0", "Activities", "Slot%20Machine")
_reg("1F3B5", "Activities", "Musical%20Note")
_reg("1F396", "Activities", "Military%20Medal")

# ── Animals & Nature ──
_reg("1F33E", "Animals%20and%20Nature", "Sheaf%20of%20Rice")
_reg("1F40D", "Animals%20and%20Nature", "Snake")
_reg("1F436", "Animals%20and%20Nature", "Dog%20Face")
_reg("1F431", "Animals%20and%20Nature", "Cat%20Face")

# ── Objects ──
_reg("1F4CA", "Objects", "Bar%20Chart")
_reg("1F4C8", "Objects", "Chart%20with%20Upwards%20Trend")
_reg("1F4C9", "Objects", "Chart%20with%20Downwards%20Trend")
_reg("1F916", "Objects", "Robot")
_reg("1F6E0", "Objects", "Hammer%20and%20Wrench")
_reg("1F52C", "Objects", "Microscope")
_reg("1F511", "Objects", "Key")
_reg("1F510", "Objects", "Locked%20with%20Key")
_reg("1F4D6", "Objects", "Open%20Book")
_reg("1F4F7", "Objects", "Camera%20with%20Flash")
_reg("1F4C1", "Objects", "File%20Folder")
_reg("1F5C3", "Objects", "File%20Cabinet")
_reg("1F4BE", "Objects", "Floppy%20Disk")
_reg("1F4E1", "Objects", "Satellite%20Antenna")
_reg("1F517", "Objects", "Link")
_reg("1F9E0", "Objects", "Brain")
_reg("1F91D", "Objects", "Handshake")
_reg("1F4D0", "Objects", "Triangular%20Ruler")
_reg("1F3A8", "Objects", "Artist%20Palette")
_reg("1F504", "Objects", "Repeat%20Button")
_reg("1F4DA", "Objects", "Books")
_reg("1F52E", "Objects", "Crystal%20Ball")
_reg("1F4DC", "Objects", "Scroll")
_reg("1F48E", "Objects", "Gem%20Stone")
_reg("1F4B0", "Objects", "Money%20Bag")
_reg("1F4AC", "Objects", "Speech%20Balloon")
_reg("1F4A1", "Objects", "Light%20Bulb")
_reg("1F4D1", "Objects", "Bookmark%20Tabs")
_reg("1F4C5", "Objects", "Calendar")
_reg("1F4CB", "Objects", "Clipboard")
_reg("1F50D", "Objects", "Magnifying%20Glass%20Tilted%20Left")
_reg("1F4F0", "Objects", "Newspaper")
_reg("1F9ED", "Objects", "Compass")
_reg("1F9F5", "Objects", "Shopping%20Cart")
_reg("1F525", "Objects", "Fire")
_reg("1F4A5", "Objects", "Collision")
_reg("1F4DD", "Objects", "Memo")
_reg("1F512", "Objects", "Locked")
_reg("1F513", "Objects", "Unlocked")
_reg("1F4A2", "Objects", "Anger%20Symbol")
_reg("1F4E2", "Objects", "Loudspeaker")
_reg("1F514", "Objects", "Bell")
_reg("1F516", "Objects", "Bookmark")
_reg("1F4C6", "Objects", "Tear-off%20Calendar")
_reg("1F4C4", "Objects", "Document")
_reg("1F4C3", "Objects", "Page%20with%20Curl")
_reg("1F4C2", "Objects", "Open%20File%20Folder")
_reg("1F4CE", "Objects", "Paperclip")
_reg("1F50E", "Objects", "Magnifying%20Glass%20Tilted%20Right")
_reg("1F4B5", "Objects", "Dollar%20Banknote")
_reg("1F4B8", "Objects", "Money%20with%20Wings")
_reg("1F9F0", "Objects", "Toolbox")
_reg("1F4A0", "Objects", "Diamond%20Shape%20with%20a%20Dot%20Inside")
_reg("1F3F7", "Objects", "Label")
_reg("1F6CD", "Objects", "Shopping%20Bags")
_reg("1F5DE", "Objects", "Newspaper")
_reg("1F9FE", "Objects", "Receipt")
_reg("1F3ED", "Objects", "Factory")

# ── Travel & Places ──
_reg("1F680", "Travel%20and%20Places", "Rocket")
_reg("1F5FA", "Travel%20and%20Places", "World%20Map")
_reg("1F30D", "Travel%20and%20Places", "Globe%20with%20Meridians")
_reg("1F3D7", "Travel%20and%20Places", "Construction")
_reg("1F3E0", "Travel%20and%20Places", "House")
_reg("1F30F", "Travel%20and%20Places", "Globe%20Showing%20Asia-Australia")
_reg("1F5FC", "Travel%20and%20Places", "Statue%20of%20Liberty")

# ── Smileys ──
_reg("1F600", "Smileys", "Grinning%20Face")
_reg("1F609", "Smileys", "Winking%20Face")
_reg("1F60A", "Smileys", "Blushing%20Face")
_reg("1F60E", "Smileys", "Smiling%20Face%20with%20Sunglasses")
_reg("1F44D", "Smileys", "Thumbs%20Up")
_reg("1F44E", "Smileys", "Thumbs%20Down")
_reg("1F449", "Smileys", "Backhand%20Index%20Pointing%20Right")
_reg("1F448", "Smileys", "Backhand%20Index%20Pointing%20Left")
_reg("1F446", "Smileys", "Backhand%20Index%20Pointing%20Up")
_reg("1F447", "Smileys", "Backhand%20Index%20Pointing%20Down")
_reg("1F4AA", "Smileys", "Flexed%20Biceps")

# ── Symbols ──
_reg("26A0", "Symbols", "Warning")
_reg("1F6AB", "Symbols", "Prohibited")
_reg("1F51D", "Symbols", "Triangular%20Flag%20on%20Post")
_reg("1F4AF", "Symbols", "Hundred%20Points")
_reg("1F538", "Symbols", "Small%20Orange%20Diamond")
_reg("1F539", "Symbols", "Small%20Blue%20Diamond")

# ── Hearts (Objects) ──
_reg("2764", "Objects", "Red%20Heart")
_reg("1F49C", "Objects", "Purple%20Heart")
_reg("1F49A", "Objects", "Green%20Heart")
_reg("1F499", "Objects", "Blue%20Heart")
_reg("1F49B", "Objects", "Yellow%20Heart")
_reg("1F496", "Objects", "Sparkling%20Heart")
_reg("1F5A4", "Objects", "Black%20Heart")

# ── Food & Drink ──
_reg("2615", "Food%20and%20Drink", "Hot%20Beverage")
_reg("1F37A", "Food%20and%20Drink", "Beer%20Mug")
_reg("1F375", "Food%20and%20Drink", "Teacup%20Without%20Handle")

# ── Additional specific emojis used in the codebase ──
_reg("1F4F1", "Objects", "Mobile%20Phone")
_reg("1F4BB", "Objects", "Laptop")
_reg("1F5A5", "Objects", "Desktop%20Computer")
_reg("1F6A7", "Symbols", "Construction%20Sign")
_reg("1F6A8", "Objects", "Police%20Cars%20Revolving%20Light")
_reg("1F50A", "Objects", "Speaker%20High%20Volume")
_reg("1F50B", "Objects", "Battery")
_reg("1F50C", "Objects", "Electric%20Plug")
_reg("1F6B6", "Smileys", "Pedestrian")
_reg("1F6F0", "Travel%20and%20Places", "Satellite")
_reg("1F3C1", "Activities", "Chequered%20Flag")
_reg("1F3C3", "Smileys", "Running")
_reg("1F4F6", "Objects", "Antenna%20Bars")
_reg("1F4E7", "Objects", "E-Mail")

# Remaining emojis found after first pass
_reg("1F626", "Smileys", "Frowning%20Face%20with%20Open%20Mouth")  # 😦
_reg("1F419", "Animals%20and%20Nature", "Octopus")  # 🐙
_reg("2728", "Activities", "Sparkles")  # ✨
_reg("1F4F8", "Objects", "Camera%20with%20Flash")  # 📸
_reg("1F3A5", "Activities", "Movie%20Camera")  # 🎥
_reg("1F9EA", "Objects", "Test%20Tube")  # 🧪
_reg("1F501", "Symbols", "Repeat%20Button")  # 🔁
_reg("1F5C4", "Objects", "File%20Cabinet")  # 🗄️
_reg("1F39B", "Objects", "Control%20Knobs")  # 🎛️
_reg("26D3", "Objects", "Chains")  # ⛓️
_reg("23F1", "Objects", "Stopwatch")  # ⏱️
_reg("1F527", "Objects", "Wrench")  # 🔧
_reg("1F310", "Travel%20and%20Places", "Globe%20with%20Meridians")  # 🌐
_reg("2B50", "Symbols", "White%20Medium%20Star")  # ⭐
_reg("1F6A6", "Travel%20and%20Places", "Traffic%20Light")  # 🚦
_reg("1F7E2", "Symbols", "Green%20Circle")  # 🟢
_reg("23F3", "Symbols", "Hourglass%20with%20Flowing%20Sand")  # ⏳
_reg("1F433", "Animals%20and%20Nature", "Spouting%20Whale")  # 🐳
_reg("1F9F9", "Objects", "Broom")  # 🧹
_reg("1F41B", "Animals%20and%20Nature", "Bug")  # 🐛
_reg("1F4E3", "Objects", "Loudspeaker")  # 📣
_reg("2699", "Objects", "Gear")  # ⚙️
_reg("1F44B", "Smileys", "Waving%20Hand")  # 👋
_reg("267B", "Symbols", "Recycling%20Symbol")  # ♻️
_reg("1F4DE", "Objects", "Telephone%20Receiver")  # 📞
_reg("1F4F8", "Objects", "Camera%20with%20Flash")  # 📸 (duplicate)
_reg("1F4E6", "Objects", "Package")  # 📦
_reg("1F6E1", "Objects", "Shield")  # 🛡️

# Additional emojis seen in QA_AUDIT.md and other files
_reg("1F6A2", "Travel%20and%20Places", "Ship")
_reg("1F3D4", "Travel%20and%20Places", "Snow-Capped%20Mountain")
_reg("2705", "Symbols", "Check%20Mark%20Button")
_reg("274C", "Symbols", "Cross%20Mark")
_reg("2753", "Symbols", "Question%20Mark")
_reg("2757", "Symbols", "Exclamation%20Mark")
_reg("2795", "Symbols", "Plus")
_reg("2796", "Symbols", "Minus")
_reg("27B0", "Symbols", "Curly%20Loop")
_reg("3030", "Symbols", "Wavy%20Dash")

# ── Variation Selector-16 (FE0F) — strip it ──
VS16 = chr(0xFE0F)


def cdn_img(category, filename, size=20):
    """Generate CDN img tag for an emoji."""
    url = f"{CDN_BASE}/{category}/{filename}.png"
    return f'<img src="{url}" alt="" width="{size}" height="{size}" style="vertical-align:middle" />'


def replace_emojis_in_line(line):
    """Replace all emoji characters in a line with CDN img tags."""
    result = []
    i = 0
    count = 0
    
    while i < len(line):
        ch = line[i]
        
        # Strip variation selectors silently
        if ch == VS16:
            i += 1
            continue
        
        # Check if this character is an emoji we need to replace
        if ch in EMOJI_MAP:
            category, filename = EMOJI_MAP[ch]
            result.append(cdn_img(category, filename))
            i += 1
            count += 1
        else:
            result.append(ch)
            i += 1
    
    return ''.join(result), count


def process_file(filepath):
    """Process a single file, replacing emojis while skipping mermaid blocks."""
    # Read with utf-8 encoding
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    output_lines = []
    total_replaced = 0
    in_mermaid = False
    
    for line in lines:
        stripped = line.strip()
        
        # Detect mermaid blocks
        if stripped.startswith('```mermaid'):
            in_mermaid = True
            output_lines.append(line)
            continue
        if in_mermaid and stripped.startswith('```'):
            in_mermaid = False
            output_lines.append(line)
            continue
        
        # Skip mermaid content
        if in_mermaid:
            output_lines.append(line)
            continue
        
        # Replace emojis in this line
        replaced_line, count = replace_emojis_in_line(line)
        output_lines.append(replaced_line)
        total_replaced += count
    
    result = '\n'.join(output_lines)
    
    if total_replaced > 0:
        # Write back with utf-8 encoding
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"  OK {total_replaced:3d} emojis replaced in {filepath}")
    else:
        print(f"  -- No emojis found in {filepath}")
    
    return total_replaced


def main():
    base = Path.cwd()
    
    files = [
        "README.md",
        "mandi_rdd/README.md",
        "SUPPORT.md",
        "DEPLOY.md",
        ".github/welcome-post-draft.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "mandi_rdd/PROJECT_STATUS.md",
        "mandi_rdd/docs/API_KEY_SETUP.md",
        "QA_AUDIT.md",
    ]
    
    total = 0
    for f in files:
        path = base / f
        if path.exists():
            count = process_file(str(path))
            total += count
        else:
            print(f"  -- {f} not found, skipping")
    
    print(f"\n{'='*50}")
    print(f"Total: {total} emojis replaced across {len(files)} files")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
