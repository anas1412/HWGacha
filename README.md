# هيفاء وهبي Gacha Bot 👑

Mudae-style card game for Discord. Every card is a Haifa Wehbe photo.
**100 cards are included** in `images/` with hand-picked rarities and Arabic names (`seed.json`).
Any new photo you drop in later gets a random **rarity** (weighted dice) and a name from a curated list.

## Commands

| Command | What it does |
|---|---|
| `/roll` | Roll a random card. Unclaimed cards show a 💍 button for 2 minutes |
| `/collection [member]` | Your cards (or someone else's), grouped by rarity |
| `/card <name>` | Look up a card and see who owns it |
| `/top` | Leaderboard by points |
| `/divorce <name>` | Release a card you own |
| `/gift <member> <name>` | Give a card away |
| `/exchange <member> <my_card> <their_card>` | Propose a trade. The other member gets Accept / Decline buttons (5 min) |
| `/rescan` | (Manage Server) register new photos in `images/` |

## Rarity

| Tier | Roll chance | Points |
|---|---|---|
| ⚪ عادية | 50% | 1 |
| 🟢 مميزة | 28% | 3 |
| 🔵 نادرة | 14% | 8 |
| 🟣 أسطورية | 6% | 20 |
| 👑 الملكة | 2% | 50 |

Limits: **3 rolls per day**, **1 claim per day**. Both reset at **midnight**, local time of the machine running the bot. Numbers live in `config.py`.

## Run locally

1. Create the bot at https://discord.com/developers/applications → New Application → Bot → **Reset Token**, copy it.
2. Same page → OAuth2 → URL Generator: scope `bot` + `applications.commands`,
   permissions `Send Messages`, `Embed Links`, `Attach Files`. Open the URL to invite the bot to your server.
3. Install and run:

```bash
pip install -r requirements.txt
```

Create a file named `.env` in this folder with one line:

```
DISCORD_TOKEN=paste_token_here
```

Then start the bot:

```bash
python3 main.py
```

On first start the bot registers the 100 seeded cards. Add more photos to `images/` later and run `/rescan`.

## Run on Replit (alternative)

Upload the folder, add `DISCORD_TOKEN` in the Secrets tab (🔒), press **Run**.
A free Repl sleeps when you close the tab; Reserved VM deployment keeps it up.

Slash commands can take up to an hour to appear the first time. Kick the bot and re-invite it if they don't show.

## Files

- `main.py` – Discord bot and commands
- `scanner.py` – registers new photos: uses `seed.json` if the file is listed there, else random (edit the name lists here)
- `seed.json` – the 100 curated cards: file, name, rarity, description. Edit names or rarities here before first run
- `db.py` – SQLite (`haifa.db`): cards, owners, cooldowns. Ownership is per server.
- `config.py` – rarities, weights, points, cooldowns
