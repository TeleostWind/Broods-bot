import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8080))


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is alive.\n")

    # silence normal logging (remove if you want logs)
    def log_message(self, format, *args):
        return


def _run_server():
    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    try:
        server.serve_forever()
    except Exception:
        # server closed or interrupted
        pass


def keep_alive():
    """Call this from your main file to start the tiny webserver in a daemon thread."""
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
main.py
(clean, minimal external imports; safe embed builder slash command)

python
Copy code
# main.py
from keep_alive import keep_alive
keep_alive()

import os
import sys
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import timezone

# --- Configuration ---
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")  # <--- set this in your environment
GUILD_ID = os.environ.get("GUILD_ID")            # optional: set to a guild id for immediate testing
# ----------------------

if not BOT_TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN environment variable not set. Exiting.")
    sys.exit(1)

UTC = timezone.utc

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        if GUILD_ID:
            # Quick sync to a single guild (fast during development)
            guild_obj = discord.Object(id=int(GUILD_ID))
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"🔗 Synced {len(synced)} commands to guild {GUILD_ID}")
        else:
            # Global sync (may take up to an hour to propagate)
            synced = await bot.tree.sync()
            print(f"🔗 Synced {len(synced)} global commands")
    except Exception as e:
        print(f"⚠️ Error syncing commands: {e}")


# ---------- Helpers ----------
def _is_valid_url(u: Optional[str]) -> bool:
    return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))


def _truncate(s: Optional[str], max_len: int):
    if s is None:
        return None, None
    s = str(s)
    if len(s) <= max_len:
        return s, None
    return s[: max_len - 3] + "...", f"Truncated text to {max_len} characters."


def _parse_color(color_str: Optional[str]):
    """
    Returns (discord.Color, warning_or_None)
    Accepts named colors (blue, red, green, yellow, purple, orange)
    or hex like '#3498db', '3498db', '0x3498db', 'abc' (3-digit).
    On parse failure returns default color and a warning string.
    """
    default = discord.Color.default()
    if not color_str:
        return default, None

    color_map = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "yellow": discord.Color.yellow(),
        "purple": discord.Color.purple(),
        "orange": discord.Color.orange(),
        "blurple": discord.Color.blurple(),
    }
    lower = color_str.lower().strip()
    if lower in color_map:
        return color_map[lower], None

    s = lower.replace("0x", "").lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return default, f"Invalid hex color '{color_str}'. Using default color."
    try:
        value = int(s, 16)
        return discord.Color(value), None
    except ValueError:
        return default, f"Invalid hex color '{color_str}'. Using default color."


# Discord limits
MAX_TITLE = 256
MAX_DESC = 4096
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024
MAX_FOOTER = 2048


# ========== Embed slash command ==========
@bot.tree.command(name="embed", description="Create a fully custom embed")
@app_commands.describe(
    title="Title of the embed",
    description="Description of the embed",
    color="Color (name like 'blue' or hex like '#3498db')",
    image="Image URL (https://...)",
    thumbnail="Thumbnail URL (https://...)",
    footer="Footer text",
    field1_name="Field 1 name",
    field1_value="Field 1 value",
    field2_name="Field 2 name",
    field2_value="Field 2 value",
    field3_name="Field 3 name",
    field3_value="Field 3 value",
)
async def embed_command(
    interaction: discord.Interaction,
    title: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = "blue",
    image: Optional[str] = None,
    thumbnail: Optional[str] = None,
    footer: Optional[str] = None,
    field1_name: Optional[str] = None,
    field1_value: Optional[str] = None,
    field2_name: Optional[str] = None,
    field2_value: Optional[str] = None,
    field3_name: Optional[str] = None,
    field3_value: Optional[str] = None,
):
    """
    Build and send an embed. Fields only added if both name+value are provided.
    If nothing meaningful is provided, sends an ephemeral error message.
    """

    warnings = []

    # require at least something to show
    has_any_content = any(
        [
            title and title.strip(),
            description and description.strip(),
            image and image.strip(),
            thumbnail and thumbnail.strip(),
            (field1_name and field1_value),
            (field2_name and field2_value),
            (field3_name and field3_value),
        ]
    )
    if not has_any_content:
        await interaction.response.send_message(
            "You must provide at least one of: title, description, image, thumbnail, or a field (name+value).",
            ephemeral=True,
        )
        return

    # parse color
    embed_color, color_warn = _parse_color(color)
    if color_warn:
        warnings.append(color_warn)

    # truncate / validate text pieces
    title, w = _truncate(title, MAX_TITLE)
    if w:
        warnings.append(w)
    description, w = _truncate(description, MAX_DESC)
    if w:
        warnings.append(w)
    footer, w = _truncate(footer, MAX_FOOTER)
    if w:
        warnings.append(w)

    # validate image/thumb urls
    if image and not _is_valid_url(image):
        warnings.append("Image URL ignored (must start with http/https).")
        image = None
    if thumbnail and not _is_valid_url(thumbnail):
        warnings.append("Thumbnail URL ignored (must start with http/https).")
        thumbnail = None

    # build embed
    try:
        embed_kwargs = {}
        if title:
            embed_kwargs["title"] = title
        if description:
            embed_kwargs["description"] = description

        embed = discord.Embed(color=embed_color, **embed_kwargs)

        # set author with bot avatar (if available)
        try:
            avatar_url = bot.user.display_avatar.url
        except Exception:
            avatar_url = None
        embed.set_author(name=str(bot.user), icon_url=avatar_url)

        if image:
            embed.set_image(url=image)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if footer:
            embed.set_footer(text=footer)
        else:
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        # fields (only if both name & value present). truncate them too.
        if field1_name and field1_value:
            n, w = _truncate(field1_name, MAX_FIELD_NAME)
            if w:
                warnings.append(w)
            v, w = _truncate(field1_value, MAX_FIELD_VALUE)
            if w:
                warnings.append(w)
            embed.add_field(name=n, value=v, inline=False)

        if field2_name and field2_value:
            n, w = _truncate(field2_name, MAX_FIELD_NAME)
            if w:
                warnings.append(w)
            v, w = _truncate(field2_value, MAX_FIELD_VALUE)
            if w:
                warnings.append(w)
            embed.add_field(name=n, value=v, inline=False)

        if field3_name and field3_value:
            n, w = _truncate(field3_name, MAX_FIELD_NAME)
            if w:
                warnings.append(w)
            v, w = _truncate(field3_value, MAX_FIELD_VALUE)
            if w:
                warnings.append(w)
            embed.add_field(name=n, value=v, inline=False)

        # send the embed
        await interaction.response.send_message(embed=embed)

        # if there are warnings, send them as an ephemeral followup so the user sees them
        if warnings:
            # truncate warnings message to avoid hitting message limits
            warn_msg = "\n".join(warnings)
            if len(warn_msg) > 1900:
                warn_msg = warn_msg[:1897] + "..."
            await interaction.followup.send(f"⚠️ Warnings:\n{warn_msg}", ephemeral=True)

    except Exception as e:
        # If embed construction or sending failed, notify the user (ephemeral)
        err_text = f"Failed to create/send embed: {e}"
        try:
            await interaction.response.send_message(err_text, ephemeral=True)
        except Exception:
            # if response already used and followup errors, just log to console
            print(err_text)


# Run the bot
bot.run(BOT_TOKEN)
