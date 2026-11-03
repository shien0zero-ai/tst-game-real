#!/usr/bin/env python3
"""Build the bundled Japanese menu font from an installed Noto CJK collection.

Requires Python fontTools. The generated font is a renamed OFL subset; it does
not depend on fonts installed on the player's PC. No downloads are performed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTCollection, TTFont

ROOT = Path(__file__).resolve().parents[1]
FAMILY = "Firing Range UI JP"
POSTSCRIPT = "FiringRangeUIJP-Regular"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"))
    parser.add_argument("--output", type=Path,
                        default=ROOT / "assets" / "fonts" / "menu_jp.otf")
    args = parser.parse_args()
    if args.source.suffix.lower() in (".ttc", ".otc"):
        collection = TTCollection(args.source, lazy=True)
        face = next((i for i, candidate in enumerate(collection.fonts)
                     if candidate["name"].getDebugName(6) == "NotoSansCJKjp-Regular"), None)
        collection.close()
        if face is None:
            parser.error("The source collection must contain NotoSansCJKjp-Regular.")
        font = TTFont(args.source, fontNumber=face, recalcTimestamp=False)
    else:
        font = TTFont(args.source, recalcTimestamp=False)

    # Kana and punctuation remain available for future menu wording; current
    # game scripts and play instructions supply the needed Japanese ideographs.
    characters = set(range(0x20, 0x7F))
    characters.update(range(0x3000, 0x3100))
    characters.update(range(0xFF00, 0xFFF0))
    sources = sorted((ROOT / "scripts").glob("*.gd"))
    sources += [ROOT / "README.md", ROOT / "docs" / "PLAY-WINDOWS.txt"]
    for path in sources:
        if path.is_file():
            characters.update(ord(char) for char in path.read_text(encoding="utf-8") if ord(char) >= 0x20)

    options = subset.Options()
    options.hinting = False
    options.layout_features = ["*"]
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
    options.name_legacy = True
    options.name_languages = ["*"]
    options.notdef_glyph = True
    options.notdef_outline = True
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(characters))
    subsetter.subset(font)

    # Use a distinct family and PostScript name for this modified font, while
    # preserving the original copyright and OFL license records.
    names = {1: FAMILY, 2: "Regular", 3: POSTSCRIPT + ";subset-1", 4: FAMILY + " Regular",
             6: POSTSCRIPT, 16: FAMILY, 17: "Regular"}
    table = font["name"]
    table.names = [record for record in table.names if record.nameID not in names]
    for name_id, text in names.items():
        table.setName(text, name_id, 3, 1, 0x409)
        table.setName(text, name_id, 1, 0, 0)
    if "CFF " in font:
        cff = font["CFF "].cff
        cff.fontNames = [POSTSCRIPT]
        cff.topDictIndex[0].FamilyName = FAMILY
        cff.topDictIndex[0].FullName = FAMILY + " Regular"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    font.save(args.output)
    glyph_count = len(font.getGlyphOrder())
    font.close()
    print(f"Japanese UI font: {args.output} ({args.output.stat().st_size:,} bytes, {glyph_count} glyphs)")


if __name__ == "__main__":
    main()
