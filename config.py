"""Game settings. Edit freely."""

# Rarity tiers, lowest to highest.
# weight  = how often /roll lands on this tier (relative)
# points  = score in /top
RARITIES = {
    "عادية":    {"weight": 50, "points": 1,  "emoji": "⚪", "color": 0x95A5A6},
    "مميزة":    {"weight": 28, "points": 3,  "emoji": "🟢", "color": 0x2ECC71},
    "نادرة":    {"weight": 14, "points": 8,  "emoji": "🔵", "color": 0x3498DB},
    "أسطورية":  {"weight": 6,  "points": 20, "emoji": "🟣", "color": 0x9B59B6},
    "الملكة":   {"weight": 2,  "points": 50, "emoji": "👑", "color": 0xF1C40F},
}

ROLLS_PER_DAY = 3            # rolls each player gets per day
# One claim per player per day (fixed).
# Both reset at midnight, local time of the machine running the bot.
CLAIM_WINDOW_SECONDS = 30    # how long the claim button stays alive after a roll
ROLL_ONLY_UNCLAIMED = True   # True: /roll only shows cards nobody in the server owns yet

IMAGES_DIR = "images"
# Optional: serve card images from a public URL instead of uploading them as attachments.
# Example (only works if the GitHub repo is PUBLIC):
#   IMAGE_BASE_URL = "https://raw.githubusercontent.com/anas1412/Haifu-Rolls/main/images"
IMAGE_BASE_URL = "https://raw.githubusercontent.com/anas1412/Haifu-Rolls/main/images"
DB_PATH = "haifa.db"
