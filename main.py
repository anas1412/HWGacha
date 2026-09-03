"""Haifa Wehbe gacha bot - Mudae-style rolling and claiming, no currency."""
import logging
import os
import random
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

import db
import scanner
from config import CLAIM_WINDOW_SECONDS, IMAGE_BASE_URL, IMAGES_DIR, RARITIES, ROLLS_PER_DAY

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("bot")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())


# ---------- helpers ----------

def card_embed(card, owner_id=None):
    r = RARITIES[card["rarity"]]
    e = discord.Embed(title=f"{r['emoji']} {card['name']}", description=card["description"], color=r["color"])
    e.add_field(name="الندرة", value=card["rarity"])
    e.add_field(name="المالك", value=f"<@{owner_id}>" if owner_id else "متاحة 💍")
    if IMAGE_BASE_URL:
        e.set_image(url=f"{IMAGE_BASE_URL.rstrip('/')}/{card['file']}")
    else:
        e.set_image(url=f"attachment://{card['file']}")
    return e


def card_kwargs(card):
    """Extra send() arguments: the image as an attachment unless IMAGE_BASE_URL is set."""
    if IMAGE_BASE_URL:
        return {}
    return {"file": discord.File(os.path.join(IMAGES_DIR, card["file"]), filename=card["file"])}


def pick_card():
    pool = db.pool_counts()
    tiers = [t for t in RARITIES if pool.get(t)]
    if not tiers:
        return None
    tier = random.choices(tiers, weights=[RARITIES[t]["weight"] for t in tiers])[0]
    return random.choice(db.cards_in_rarity(tier))


def fmt_wait(seconds):
    m = int(seconds // 60)
    return f"{m // 60} س {m % 60} د" if m >= 60 else f"{m} د"


class ClaimView(discord.ui.View):
    def __init__(self, card):
        super().__init__(timeout=CLAIM_WINDOW_SECONDS)
        self.card = card
        self.message = None

    @discord.ui.button(label="اطلبها 💍", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid, uid = interaction.guild_id, interaction.user.id
        if db.claimed_today(gid, uid):
            await interaction.response.send_message(
                f"⏳ استخدمت طلب اليوم. يتجدد بعد {fmt_wait(db.seconds_until_midnight())}", ephemeral=True
            )
            return
        if not db.claim(gid, self.card["id"], uid):
            await interaction.response.send_message("💔 سبقك أحد إليها", ephemeral=True)
            return
        button.disabled = True
        self.stop()
        await interaction.response.edit_message(embed=card_embed(self.card, uid), view=self)
        await interaction.followup.send(f"💍 {interaction.user.mention} حصل على **{self.card['name']}**!")

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ExchangeView(discord.ui.View):
    def __init__(self, offerer, target, my_card, their_card):
        super().__init__(timeout=300)
        self.offerer, self.target = offerer, target
        self.my_card, self.their_card = my_card, their_card
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("هذا العرض ليس لك", ephemeral=True)
            return False
        return True

    async def _finish(self, interaction, text):
        for item in self.children:
            item.disabled = True
        self.stop()
        await interaction.response.edit_message(content=text, embed=None, view=self)

    @discord.ui.button(label="قبول 🤝", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            db.swap(interaction.guild_id, self.my_card["id"], self.offerer.id, self.their_card["id"], self.target.id)
        except sqlite3.IntegrityError:
            await self._finish(interaction, "❌ تغيّرت الملكية، العرض لم يعد صالحاً")
            return
        await self._finish(
            interaction,
            f"🤝 تم التبادل! {self.offerer.mention} أخذ **{self.their_card['name']}** "
            f"و{self.target.mention} أخذ **{self.my_card['name']}**",
        )

    @discord.ui.button(label="رفض", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish(interaction, f"❌ {self.target.mention} رفض التبادل")

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⌛ انتهى وقت العرض", embed=None, view=self)
            except discord.HTTPException:
                pass


# ---------- events ----------

COMMANDS = None  # snapshot of the command definitions, taken once on first connect


async def sync_guild(guild):
    """Register the commands on one server. Per-server commands show up instantly."""
    for cmd in COMMANDS:
        bot.tree.add_command(cmd, guild=guild, override=True)
    await bot.tree.sync(guild=guild)


@bot.event
async def on_ready():
    global COMMANDS
    db.init()
    if COMMANDS is None:
        COMMANDS = list(bot.tree.get_commands())
        # Drop the global copies on Discord, otherwise every command appears twice.
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
    for guild in bot.guilds:
        await sync_guild(guild)
    log.info("logged in as %s, commands synced to %d server(s)", bot.user, len(bot.guilds))


@bot.event
async def on_guild_join(guild):
    await sync_guild(guild)
    log.info("joined %s, commands synced", guild.name)


# ---------- commands ----------

@bot.tree.command(description="ارمي كرت هيفاء عشوائي")
async def roll(interaction: discord.Interaction):
    gid, uid = interaction.guild_id, interaction.user.id
    used = db.rolls_today(gid, uid)
    if used >= ROLLS_PER_DAY:
        await interaction.response.send_message(
            f"⏳ خلصت رميّات اليوم. تتجدد بعد {fmt_wait(db.seconds_until_midnight())}", ephemeral=True
        )
        return
    card = pick_card()
    if card is None:
        await interaction.response.send_message("ما في كروت بعد. حطّ صور في مجلد images وجرّب /rescan", ephemeral=True)
        return
    db.record_roll(gid, uid)
    owner = db.owner_of(gid, card["id"])
    embed = card_embed(card, owner)
    embed.set_footer(text=f"رميّات متبقية اليوم: {ROLLS_PER_DAY - used - 1}/{ROLLS_PER_DAY}")
    if owner:
        await interaction.response.send_message(embed=embed, **card_kwargs(card))
        return
    view = ClaimView(card)
    await interaction.response.send_message(embed=embed, view=view, **card_kwargs(card))
    view.message = await interaction.original_response()


@bot.tree.command(description="شوف مجموعتك أو مجموعة عضو")
@app_commands.describe(member="العضو (اختياري)")
async def collection(interaction: discord.Interaction, member: discord.Member | None = None):
    member = member or interaction.user
    cards = db.collection(interaction.guild_id, member.id)
    if not cards:
        await interaction.response.send_message(f"{member.display_name} ما عنده كروت بعد 🥲")
        return
    points = sum(RARITIES[c["rarity"]]["points"] for c in cards)
    e = discord.Embed(title=f"مجموعة {member.display_name}", color=0xE91E63)
    e.set_footer(text=f"{len(cards)} كرت · {points} نقطة")
    for tier in reversed(list(RARITIES)):
        names = [c["name"] for c in cards if c["rarity"] == tier]
        if names:
            shown = names[:15]
            more = f"\n… و{len(names) - 15} غيرها" if len(names) > 15 else ""
            e.add_field(name=f"{RARITIES[tier]['emoji']} {tier} ({len(names)})", value="\n".join(shown) + more, inline=False)
    await interaction.response.send_message(embed=e)


@bot.tree.command(description="ابحث عن كرت بالاسم")
@app_commands.describe(name="اسم الكرت أو جزء منه")
async def card(interaction: discord.Interaction, name: str):
    c = db.find_card(name)
    if not c:
        await interaction.response.send_message("ما لقيت كرت بهذا الاسم", ephemeral=True)
        return
    owner = db.owner_of(interaction.guild_id, c["id"])
    await interaction.response.send_message(embed=card_embed(c, owner), **card_kwargs(c))


@bot.tree.command(description="قائمة المتصدرين")
async def top(interaction: discord.Interaction):
    board = db.leaderboard(interaction.guild_id)
    if not board:
        await interaction.response.send_message("ما حد طلب شي بعد")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"{medals[i] if i < 3 else f'{i + 1}.'} <@{uid}> — {pts} نقطة · {cnt} كرت"
        for i, (uid, (pts, cnt)) in enumerate(board)
    ]
    await interaction.response.send_message(embed=discord.Embed(title="👑 المتصدرون", description="\n".join(lines), color=0xF1C40F))


@bot.tree.command(description="تخلَّ عن كرت من مجموعتك")
@app_commands.describe(name="اسم الكرت")
async def divorce(interaction: discord.Interaction, name: str):
    c = db.find_card(name)
    if not c or not db.release(interaction.guild_id, c["id"], interaction.user.id):
        await interaction.response.send_message("هذا الكرت ليس في مجموعتك", ephemeral=True)
        return
    await interaction.response.send_message(f"💔 {interaction.user.mention} تخلّى عن **{c['name']}**")


@bot.tree.command(description="اهدِ كرت لعضو")
@app_commands.describe(member="المستلم", name="اسم الكرت")
async def gift(interaction: discord.Interaction, member: discord.Member, name: str):
    c = db.find_card(name)
    if not c or not db.transfer(interaction.guild_id, c["id"], interaction.user.id, member.id):
        await interaction.response.send_message("هذا الكرت ليس في مجموعتك", ephemeral=True)
        return
    await interaction.response.send_message(f"🎁 {interaction.user.mention} أهدى **{c['name']}** إلى {member.mention}")


@bot.tree.command(description="اعرض تبادل كرت بكرت مع عضو")
@app_commands.describe(member="الطرف الآخر", my_card="كرتك الذي تعرضه", their_card="كرته الذي تريده")
async def exchange(interaction: discord.Interaction, member: discord.Member, my_card: str, their_card: str):
    gid, uid = interaction.guild_id, interaction.user.id
    if member.id == uid:
        await interaction.response.send_message("ما تقدر تتبادل مع نفسك", ephemeral=True)
        return
    mine, theirs = db.find_card(my_card), db.find_card(their_card)
    if not mine or db.owner_of(gid, mine["id"]) != uid:
        await interaction.response.send_message("الكرت الأول ليس في مجموعتك", ephemeral=True)
        return
    if not theirs or db.owner_of(gid, theirs["id"]) != member.id:
        await interaction.response.send_message(f"الكرت الثاني ليس في مجموعة {member.display_name}", ephemeral=True)
        return
    e = discord.Embed(title="🤝 عرض تبادل", color=0x3498DB)
    e.add_field(name=f"{interaction.user.display_name} يعطي", value=f"{RARITIES[mine['rarity']]['emoji']} {mine['name']}")
    e.add_field(name=f"{member.display_name} يعطي", value=f"{RARITIES[theirs['rarity']]['emoji']} {theirs['name']}")
    e.set_footer(text="العرض صالح 5 دقائق")
    view = ExchangeView(interaction.user, member, mine, theirs)
    await interaction.response.send_message(content=member.mention, embed=e, view=view)
    view.message = await interaction.original_response()


@bot.tree.command(description="(إدارة) افحص الصور الجديدة في مجلد images")
@app_commands.default_permissions(manage_guild=True)
async def rescan(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    new, failed = await scanner.scan_new_images()
    pool = db.pool_counts()
    lines = [f"✅ {len(new)} كرت جديد", f"⚠️ {len(failed)} صورة فشلت" if failed else ""]
    lines += [f"{RARITIES[c['rarity']]['emoji']} {c['name']} — {c['rarity']}" for c in new[:20]]
    lines.append("\nالمجموع: " + " · ".join(f"{RARITIES[t]['emoji']} {pool.get(t, 0)}" for t in RARITIES))
    await interaction.followup.send("\n".join(l for l in lines if l), ephemeral=True)


def load_token():
    """DISCORD_TOKEN from the environment, else from a .env file next to this script."""
    if os.environ.get("DISCORD_TOKEN"):
        return os.environ["DISCORD_TOKEN"]
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                key, _, value = line.strip().partition("=")
                if key == "DISCORD_TOKEN" and value:
                    return value.strip().strip('"').strip("'")
    raise SystemExit("DISCORD_TOKEN not set. Put it in .env as DISCORD_TOKEN=... or export it.")


if __name__ == "__main__":
    bot.run(load_token())
