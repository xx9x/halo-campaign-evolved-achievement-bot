import asyncio
import os
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from auth import XboxAuthenticationError, XboxAuthenticator
from xbox import HaloAchievementClient, XboxAPIError


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DISCORD_OWNER_ID = os.getenv("DISCORD_OWNER_ID")
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
HALO_TITLE_ID = os.getenv("HALO_CAMPAIGN_EVOLVED_TITLE_ID")


if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env.")

if not DISCORD_GUILD_ID:
    raise RuntimeError("DISCORD_GUILD_ID is missing from .env.")

if not MICROSOFT_CLIENT_ID:
    raise RuntimeError("MICROSOFT_CLIENT_ID is missing from .env.")

if not HALO_TITLE_ID:
    raise RuntimeError(
        "HALO_CAMPAIGN_EVOLVED_TITLE_ID is missing from .env."
    )


GUILD = discord.Object(id=int(DISCORD_GUILD_ID))

authenticator = XboxAuthenticator(MICROSOFT_CLIENT_ID)
achievement_client = HaloAchievementClient(HALO_TITLE_ID)

achievement_cache: list[dict[str, Any]] = []
xbox_account: dict[str, str] | None = None


def progress_bar(percent: float, length: int = 14) -> str:
    filled = round((percent / 100) * length)
    empty = length - filled

    return "█" * filled + "░" * empty


def achievement_description(
    achievement: dict[str, Any],
    locked: bool,
) -> str:
    if locked and achievement.get("isSecret"):
        return "Secret achievement"

    if locked:
        return str(
            achievement.get(
                "lockedDescription",
                achievement.get(
                    "description",
                    "No description available.",
                ),
            )
        )

    return str(
        achievement.get(
            "description",
            "No description available.",
        )
    )


async def authenticate_xbox(
    interaction: discord.Interaction,
) -> dict[str, str]:
    global xbox_account

    if xbox_account:
        return xbox_account

    loop = asyncio.get_running_loop()

    def show_device_message(message: str) -> None:
        asyncio.run_coroutine_threadsafe(
            interaction.followup.send(
                f"### Xbox sign-in required\n{message}",
                ephemeral=True,
            ),
            loop,
        )

    xbox_account = await asyncio.to_thread(
        authenticator.login,
        show_device_message,
    )

    return xbox_account


async def refresh_achievement_cache(
    interaction: discord.Interaction,
) -> list[dict[str, Any]]:
    global achievement_cache

    account = await authenticate_xbox(interaction)

    achievement_cache = await asyncio.to_thread(
        achievement_client.get_all_achievements,
        account,
    )

    return achievement_cache


async def ensure_achievements(
    interaction: discord.Interaction,
) -> list[dict[str, Any]]:
    if achievement_cache:
        return achievement_cache

    return await refresh_achievement_cache(interaction)


class AchievementBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self) -> None:
        self.tree.copy_global_to(guild=GUILD)
        synced = await self.tree.sync(guild=GUILD)

        print(f"Synced {len(synced)} slash command(s).")


bot = AchievementBot()


@bot.event
async def on_ready() -> None:
    print(f"Discord bot logged in as {bot.user}.")
    print("Halo: Campaign Evolved achievement bot is ready.")


@bot.tree.command(
    name="status",
    description="Check whether the Halo achievement bot is running.",
)
async def status(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        "✅ Halo: Campaign Evolved achievement bot is online.",
        ephemeral=True,
    )


@bot.tree.command(
    name="xbox-login",
    description="Sign in to the Xbox account used by this bot.",
)
async def xbox_login(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        account = await authenticate_xbox(interaction)

        await interaction.followup.send(
            "✅ Xbox authentication worked.\n"
            f"Signed in as **{account.get('gamertag', 'Xbox user')}**.",
            ephemeral=True,
        )

    except (XboxAuthenticationError, XboxAPIError) as error:
        await interaction.followup.send(
            f"❌ Xbox login failed:\n```text\n{error}\n```",
            ephemeral=True,
        )

    except Exception as error:
        await interaction.followup.send(
            f"❌ Unexpected error:\n```text\n{error}\n```",
            ephemeral=True,
        )


@bot.tree.command(
    name="achievements",
    description="Show Halo: Campaign Evolved achievement progress.",
)
async def achievements(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    try:
        achievement_list = await ensure_achievements(interaction)
        summary = achievement_client.get_summary(achievement_list)

        completion = float(summary["completion"])

        embed = discord.Embed(
            title="Halo: Campaign Evolved",
            description=(
                f"`{progress_bar(completion)}`\n"
                f"**{completion:.1f}% complete**"
            ),
        )

        embed.add_field(
            name="Achievements",
            value=(
                f"**{summary['unlocked']} / "
                f"{summary['total']}** unlocked"
            ),
            inline=True,
        )

        embed.add_field(
            name="Gamerscore",
            value=(
                f"**{summary['unlocked_gamerscore']} / "
                f"{summary['total_gamerscore']}G**"
            ),
            inline=True,
        )

        if xbox_account:
            embed.set_footer(
                text=f"Xbox account: {xbox_account.get('gamertag', '')}"
            )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        await interaction.followup.send(
            f"❌ Could not retrieve achievements:\n```text\n{error}\n```",
            ephemeral=True,
        )


@bot.tree.command(
    name="unlocked",
    description="Show unlocked Halo: Campaign Evolved achievements.",
)
async def unlocked(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    try:
        achievement_list = await ensure_achievements(interaction)

        unlocked_items = [
            achievement
            for achievement in achievement_list
            if achievement_client.is_unlocked(achievement)
        ]

        if not unlocked_items:
            await interaction.followup.send(
                "You have not unlocked any achievements yet."
            )
            return

        lines = []

        for achievement in unlocked_items[:20]:
            name = achievement.get("name", "Unknown achievement")
            score = achievement_client.get_gamerscore(achievement)
            lines.append(f"✅ **{name}** — {score}G")

        embed = discord.Embed(
            title="Unlocked Achievements",
            description="\n".join(lines),
        )

        if len(unlocked_items) > 20:
            embed.set_footer(
                text=(
                    f"Showing 20 of {len(unlocked_items)} "
                    "unlocked achievements."
                )
            )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        await interaction.followup.send(
            f"❌ Could not retrieve achievements:\n```text\n{error}\n```",
            ephemeral=True,
        )


@bot.tree.command(
    name="locked",
    description="Show locked Halo: Campaign Evolved achievements.",
)
async def locked(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    try:
        achievement_list = await ensure_achievements(interaction)

        locked_items = [
            achievement
            for achievement in achievement_list
            if not achievement_client.is_unlocked(achievement)
        ]

        if not locked_items:
            await interaction.followup.send(
                "🏆 Every achievement is unlocked."
            )
            return

        lines = []

        for achievement in locked_items[:20]:
            name = achievement.get("name", "Unknown achievement")
            score = achievement_client.get_gamerscore(achievement)
            lines.append(f"🔒 **{name}** — {score}G")

        embed = discord.Embed(
            title="Locked Achievements",
            description="\n".join(lines),
        )

        if len(locked_items) > 20:
            embed.set_footer(
                text=(
                    f"Showing 20 of {len(locked_items)} "
                    "locked achievements."
                )
            )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        await interaction.followup.send(
            f"❌ Could not retrieve achievements:\n```text\n{error}\n```",
            ephemeral=True,
        )


@bot.tree.command(
    name="achievement",
    description="Search for a Halo: Campaign Evolved achievement.",
)
@app_commands.describe(
    name="Enter all or part of the achievement name.",
)
async def achievement(
    interaction: discord.Interaction,
    name: str,
) -> None:
    await interaction.response.defer(thinking=True)

    try:
        achievement_list = await ensure_achievements(interaction)
        matches = achievement_client.search(achievement_list, name)

        if not matches:
            await interaction.followup.send(
                f'No achievement matched **"{name}"**.',
                ephemeral=True,
            )
            return

        selected = matches[0]
        unlocked_state = achievement_client.is_unlocked(selected)
        score = achievement_client.get_gamerscore(selected)

        embed = discord.Embed(
            title=str(selected.get("name", "Unknown achievement")),
            description=achievement_description(
                selected,
                locked=not unlocked_state,
            ),
        )

        embed.add_field(
            name="Status",
            value="✅ Unlocked" if unlocked_state else "🔒 Locked",
            inline=True,
        )

        embed.add_field(
            name="Gamerscore",
            value=f"{score}G",
            inline=True,
        )

        icon_url = achievement_client.get_icon_url(selected)

        if icon_url:
            embed.set_thumbnail(url=icon_url)

        if len(matches) > 1:
            embed.set_footer(
                text=(
                    f"{len(matches)} achievements matched. "
                    "Showing the closest result."
                )
            )

        await interaction.followup.send(embed=embed)

    except Exception as error:
        await interaction.followup.send(
            f"❌ Could not search achievements:\n```text\n{error}\n```",
            ephemeral=True,
        )


@bot.tree.command(
    name="refresh",
    description="Refresh achievements directly from Xbox.",
)
async def refresh(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        achievement_list = await refresh_achievement_cache(interaction)

        await interaction.followup.send(
            f"✅ Refreshed **{len(achievement_list)}** achievements.",
            ephemeral=True,
        )

    except Exception as error:
        await interaction.followup.send(
            f"❌ Refresh failed:\n```text\n{error}\n```",
            ephemeral=True,
        )


@bot.tree.command(
    name="xbox-logout",
    description="Delete the locally saved Microsoft login.",
)
async def xbox_logout(interaction: discord.Interaction) -> None:
    global xbox_account
    global achievement_cache

    if DISCORD_OWNER_ID and str(interaction.user.id) != DISCORD_OWNER_ID:
        await interaction.response.send_message(
            "Only the bot owner can log out the Xbox account.",
            ephemeral=True,
        )
        return

    authenticator.logout()
    xbox_account = None
    achievement_cache = []

    await interaction.response.send_message(
        "✅ Saved Xbox login removed. Use `/xbox-login` to sign in again.",
        ephemeral=True,
    )


bot.run(DISCORD_TOKEN)