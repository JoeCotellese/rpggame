#!/usr/bin/env python3
# ABOUTME: Script to generate placeholder 32x32 PNG sprites for testing.
# ABOUTME: Creates colored squares with category-specific colors and labels.

"""Generate placeholder sprites for testing the 2D client.

Usage:
    python scripts/generate_placeholders.py

Requires: pillow (pip install pillow)
"""

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("This script requires Pillow. Install with: pip install pillow")
    exit(1)


TILE_SIZE = 32
ASSETS_PATH = Path(__file__).parent.parent / "assets"

# Color schemes for different sprite categories
COLORS = {
    # Characters - blue tones
    "fighter": (70, 130, 180),    # Steel blue
    "rogue": (47, 79, 79),        # Dark slate
    "wizard": (138, 43, 226),     # Blue violet
    "cleric": (255, 215, 0),      # Gold
    "_fallback_humanoid": (100, 100, 100),  # Gray

    # Monsters - category colors
    "undead": (139, 69, 19),      # Saddle brown (bones)
    "beast": (34, 139, 34),       # Forest green
    "humanoid": (178, 34, 34),    # Firebrick red
    "_fallback_generic": (50, 50, 50),  # Dark gray

    # Specific monsters
    "skeleton": (245, 245, 220),  # Beige (bones)
    "zombie": (85, 107, 47),      # Dark olive
    "goblin": (154, 205, 50),     # Yellow green
    "wolf": (105, 105, 105),      # Dim gray

    # Items
    "weapon": (192, 192, 192),    # Silver
    "armor": (169, 169, 169),     # Dark gray
    "consumable": (255, 99, 71),  # Tomato red (potion)

    # Effects
    "damage": (255, 0, 0),        # Red
    "healing": (0, 255, 0),       # Green
    "status": (255, 255, 0),      # Yellow

    # Tiles
    "floor": (64, 64, 64),        # Dark gray
    "wall": (32, 32, 32),         # Very dark
}


def create_placeholder_sprite(
    color: tuple[int, int, int],
    label: str = "",
    size: int = TILE_SIZE,
    border: bool = True,
) -> Image.Image:
    """Create a simple colored square placeholder sprite.

    Args:
        color: RGB tuple for fill color
        label: Optional text label (first 2 chars shown)
        size: Sprite size in pixels
        border: Whether to add a darker border

    Returns:
        PIL Image object
    """
    img = Image.new("RGBA", (size, size), color + (255,))
    draw = ImageDraw.Draw(img)

    # Add border
    if border:
        border_color = tuple(max(0, c - 40) for c in color) + (255,)
        draw.rectangle([0, 0, size - 1, size - 1], outline=border_color, width=2)

    # Add label text (first 2 characters)
    if label:
        short_label = label[:2].upper()
        # Use default font, centered
        try:
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), short_label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (size - text_width) // 2
            y = (size - text_height) // 2
            # Draw with contrasting color
            text_color = (255, 255, 255) if sum(color) < 384 else (0, 0, 0)
            draw.text((x, y), short_label, fill=text_color, font=font)
        except Exception:
            pass  # Skip label if font issues

    return img


def generate_character_sprites():
    """Generate character class sprites."""
    chars_path = ASSETS_PATH / "sprites" / "characters"
    chars_path.mkdir(parents=True, exist_ok=True)

    characters = ["fighter", "rogue", "wizard", "cleric"]
    for char in characters:
        color = COLORS.get(char, (100, 100, 100))
        img = create_placeholder_sprite(color, char)
        img.save(chars_path / f"{char}.png")
        print(f"Created: characters/{char}.png")

    # Fallback
    img = create_placeholder_sprite(COLORS["_fallback_humanoid"], "?")
    img.save(chars_path / "_fallback_humanoid.png")
    print("Created: characters/_fallback_humanoid.png")


def generate_monster_sprites():
    """Generate monster sprites with category fallbacks."""
    monsters_path = ASSETS_PATH / "sprites" / "monsters"

    # Category-specific monsters and fallbacks
    categories = {
        "undead": ["skeleton", "zombie"],
        "beast": ["wolf"],
        "humanoid": ["goblin"],
    }

    for category, monsters in categories.items():
        cat_path = monsters_path / category
        cat_path.mkdir(parents=True, exist_ok=True)

        # Generate specific monster sprites
        for monster in monsters:
            color = COLORS.get(monster, COLORS[category])
            img = create_placeholder_sprite(color, monster)
            img.save(cat_path / f"{monster}.png")
            print(f"Created: monsters/{category}/{monster}.png")

        # Generate category fallback
        color = COLORS[category]
        img = create_placeholder_sprite(color, "?")
        img.save(cat_path / "_fallback.png")
        print(f"Created: monsters/{category}/_fallback.png")

    # Generic fallback
    img = create_placeholder_sprite(COLORS["_fallback_generic"], "??")
    img.save(monsters_path / "_fallback_generic.png")
    print("Created: monsters/_fallback_generic.png")


def generate_tile_sprites():
    """Generate basic tileset sprites."""
    tiles_path = ASSETS_PATH / "tilesets"
    tiles_path.mkdir(parents=True, exist_ok=True)

    # Create a simple tileset image (2x2 grid of basic tiles)
    tileset_size = TILE_SIZE * 4  # 4x4 tiles
    tileset = Image.new("RGBA", (tileset_size, tileset_size), (0, 0, 0, 0))

    # Floor tile (0,0)
    floor = create_placeholder_sprite(COLORS["floor"], "FL", border=False)
    tileset.paste(floor, (0, 0))

    # Wall tile (1,0)
    wall = create_placeholder_sprite(COLORS["wall"], "WL", border=False)
    tileset.paste(wall, (TILE_SIZE, 0))

    tileset.save(tiles_path / "dungeon_basic.png")
    print("Created: tilesets/dungeon_basic.png")


def generate_effect_sprites():
    """Generate effect sprites."""
    effects_path = ASSETS_PATH / "sprites" / "effects"

    categories = ["damage", "healing", "status"]
    for cat in categories:
        cat_path = effects_path / cat
        cat_path.mkdir(parents=True, exist_ok=True)

        color = COLORS[cat]
        img = create_placeholder_sprite(color, cat[:2])
        img.save(cat_path / "_fallback.png")
        print(f"Created: effects/{cat}/_fallback.png")


def main():
    """Generate all placeholder sprites."""
    print(f"Generating placeholder sprites in: {ASSETS_PATH}")
    print(f"Tile size: {TILE_SIZE}x{TILE_SIZE}")
    print()

    generate_character_sprites()
    print()

    generate_monster_sprites()
    print()

    generate_tile_sprites()
    print()

    generate_effect_sprites()
    print()

    print("Done! Placeholder sprites generated.")


if __name__ == "__main__":
    main()
