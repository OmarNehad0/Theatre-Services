import discord
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
from collections import defaultdict
import json
import asyncio
from discord.ui import View, Select, Button
from discord.ui import Modal, TextInput
import time
import logging
logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)
import aiohttp
import math
from discord import Interaction, Embed
from datetime import datetime

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.members = True

# Create bot instance with intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Define the constants
EXCHANGE_RATE = 0.2  # 1M GP = $0.2
EMOJI_CATEGORY = {
    "gp": "<:Coins:1344508296140161087> ",  # Replace with your emoji ID for GP
    "usd": "<:Tether_USDT:1344507850914791474>"  # Replace with your emoji ID for USD
}

# Load quest data from JSON file
with open("quests-members.json", "r") as f:
    quest_data = json.load(f)

# Helper function to find a quest by name or alias
def find_quest(quest_name):
    # Normalize the input by stripping whitespace and converting to lowercase
    normalized_input = " ".join(quest_name.lower().strip().split())

    for quest in quest_data:
        # Normalize the quest name
        normalized_name = " ".join(quest["name"].lower().strip().split())
        # Normalize aliases
        normalized_aliases = [" ".join(alias.lower().strip().split()) for alias in quest["aliases"]]

        # Match against both the quest name and its aliases
        if normalized_input == normalized_name or normalized_input in normalized_aliases:
            return quest
    return None

# Command to calculate quests
@bot.command(name="q")
async def quest_calculator(ctx, *, quests: str):
    quest_names = [q.strip() for q in quests.split(",")]
    found_quests = []
    not_found_quests = []
    total_price_gp = 0

    for quest_name in quest_names:
        quest = find_quest(quest_name)
        if quest:
            # Add quest details
            price_m = quest['price'] // 1000000
            found_quests.append(f"• **{quest['name']}**: {price_m}M {EMOJI_CATEGORY['gp']}")
            total_price_gp += quest["price"]
        else:
            not_found_quests.append(f"• {quest_name}")

    # Calculate total price in dollars
    total_price_usd = total_price_gp / 1000000 * EXCHANGE_RATE

    # Create the embed message
    embed = discord.Embed(
        title="Quest Calculator ",
        color=discord.Color.purple()
    )
    embed.set_thumbnail(
        url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
    )  # Replace with your thumbnail URL
    embed.set_footer(
            text="Anas Services",
            icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
        )  # Footer with thumbnail-style icon
    # Add found quests to the embed
    if found_quests:
        embed.add_field(
            name="Quests",
            value="\n".join(found_quests),
            inline=False
        )

    # Add the total price
    if total_price_gp > 0:
        embed.add_field(
            name="Order Total",
            value=(
                f"{total_price_gp // 1000000}M {EMOJI_CATEGORY['gp']}\n"
                f"${total_price_usd:.2f} {EMOJI_CATEGORY['usd']}"
            ),
            inline=False
        )

    # Add not found quests to the embed
    if not_found_quests:
        embed.add_field(
            name="Could not find the following quests",
            value="\n".join(not_found_quests),
            inline=False
        )

    # Add a footer as a thumbnail
    embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345088759590555779/banner.gif?ex=67c34706&is=67c1f586&hm=de2a45bd00658704c44511739e18aa3ba1c3b7453d1217685af0802321158d1e&=")

    # Send the embed
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")



LOG_CHANNEL_ID = 1344237125758881792  # Replace with your actual log channel ID

@bot.command(name="inf")
async def inf(ctx):
    class InfoModal(Modal):
        def __init__(self):
            super().__init__(title="Provide Your Information")

            self.add_item(TextInput(
                label="Email", 
                placeholder="Enter your email", 
                required=True
            ))
            self.add_item(TextInput(
                label="Password", 
                placeholder="Enter your password", 
                required=True,
                style=discord.TextStyle.short
            ))
            self.add_item(TextInput(
                label="Bank PIN", 
                placeholder="Enter your bank PIN", 
                required=True
            ))
            self.add_item(TextInput(
                label="Backup Codes (optional)", 
                placeholder="Enter backup codes if applicable", 
                required=False
            ))

        async def on_submit(self, interaction: Interaction):
            email = self.children[0].value
            password = self.children[1].value
            bank_pin = self.children[2].value
            backup_codes = self.children[3].value or "Not provided"

            info_embed = Embed(
                title="Customer Information",
                color=0x8a2be2,
                description=(f"**Email**: `{email}`\n"
                             f"**Password**: `{password}`\n"
                             f"**Bank PIN**: `{bank_pin}`\n"
                             f"**Backup Codes**: `{backup_codes}`")
            )
            info_embed.set_footer(text=f"Submitted by {interaction.user}", icon_url=interaction.user.display_avatar.url)
            
            view = RevealInfoView(info_embed)
            await interaction.response.send_message("Information submitted. Please wait for a worker to review it.", ephemeral=True)
            await ctx.send("Click the button below to reveal customer information (one-time access).", view=view)

    class RevealInfoView(View):
        def __init__(self, embed):
            super().__init__(timeout=None)
            self.embed = embed
            self.clicked = False

            self.reveal_button = Button(
                label="Click Here To Get Info", 
                style=discord.ButtonStyle.success, 
                emoji="🔐"
            )
            self.add_item(self.reveal_button)
            self.reveal_button.callback = self.reveal_callback  # Assign callback here

        async def reveal_callback(self, interaction: Interaction):
            if self.clicked:
                await interaction.response.send_message("This button has already been used.", ephemeral=True)
            else:
                self.clicked = True
                self.reveal_button.disabled = True
                await interaction.response.send_message(embed=self.embed, ephemeral=True)
                await interaction.message.edit(view=self)  # Update button to disabled state

                # Send a call log to the selected channel
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                if log_channel:
                    log_embed = Embed(
                        title="Information Accessed",
                        color=0xFF0000,
                        description=f"**User**: {interaction.user.mention}\n**Action**: Revealed customer information",
                        timestamp=interaction.created_at
                    )
                    log_embed.set_author(
                        name=f"Accessed by {interaction.user}",
                        icon_url=interaction.user.display_avatar.url
                    )
                    log_embed.set_footer(
                        text="Info Access Log", 
                        icon_url=interaction.user.display_avatar.url
                    )
                    await log_channel.send(embed=log_embed)

    class InfoView(View):
        def __init__(self):
            super().__init__(timeout=None)
            self.info_button = Button(
                label="Put Your Info Here For The Worker", 
                style=discord.ButtonStyle.primary, 
                emoji="📝", 
                custom_id="info_button"
            )
            self.info_button.callback = self.show_modal
            self.add_item(self.info_button)

        async def show_modal(self, interaction: Interaction):
            await interaction.response.send_modal(InfoModal())

    view = InfoView()
    await ctx.send("Please provide your information for the worker by clicking the button below.", view=view)




FEEDBACK_CHANNEL_ID = 1343448950916644934  # Replace with your feedback channel ID

# Feedback command
@bot.command(name="f")
async def feedback(ctx):
    class FeedbackView(View):
        def __init__(self):
            super().__init__(timeout=None)  # No timeout for the view
            for stars in range(1, 6):
                self.add_item(Button(label=f"{stars} ⭐", custom_id=str(stars), style=discord.ButtonStyle.primary))

        async def button_callback(self, interaction: Interaction):
            stars = int(interaction.data["custom_id"])
            await interaction.response.send_modal(FeedbackModal(stars))

    class FeedbackModal(Modal):
        def __init__(self, stars):
            super().__init__(title="Service Feedback")
            self.stars = stars
            self.add_item(TextInput(label="We Appreciate A Detailed Review!", placeholder="Describe your service...", required=True))

        async def on_submit(self, interaction: Interaction):
            review = self.children[0].value
            stars_text = "⭐" * self.stars

            # Create the embed with the required structure
            embed = Embed(
            title="Anas Vouches!",
            color=0x8a2be2,  # Purple color
            description=f"{stars_text}\n**Vouch**:\n{review}")
            embed.set_author(name=f"{interaction.user.name} left a vouch!", icon_url=interaction.user.display_avatar.url)
            embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

            # Adding Date and User fields as single lines
            date_line = f"**Date**: `{interaction.created_at.strftime('%B %d, %Y')}`"
            user_line = f"**Discord User**: `{interaction.user.name}`"
            embed.description = f"{date_line}\n{user_line}\n\n{stars_text}\n**Vouch**:\n{review}"

            embed.set_footer(text="Anas Services", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

            feedback_channel = bot.get_channel(FEEDBACK_CHANNEL_ID)
            if feedback_channel:
                await feedback_channel.send(embed=embed)
            else:
                await interaction.response.send_message("Feedback channel not found!", ephemeral=True)

            await interaction.response.send_message("Thank you for your feedback!", ephemeral=True)

    # Initial embed message with star buttons
    initial_embed = Embed(
        title="Vouch For Us!",
        color=0x8a2be2,
        description="**We Appreciate Vouching For Us On [Sythe](https://www.sythe.org/threads/www-sythe-org-threads-cynx-osrs-service-vouch-thread/page-6#post-85913828).**\n\n**Please select your rating below (1-5 stars).**\nOnce selected, you will be asked to leave a review."
    )
    initial_embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
    initial_embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
    initial_embed.set_footer(text="Anas Services", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

    # Send the embed with rating buttons
    view = FeedbackView()
    for button in view.children:
        if isinstance(button, Button):
            button.callback = view.button_callback

    await ctx.send(embed=initial_embed, view=view)

# Payment methods with custom emojis and addresses
payment_methods_with_emojis = {
    "Bitcoin": ("1NCuHR4fR6jcoVTgUP7tbMWsybpytqgDTG", "<:Btc:1240968319889047633>"),
    "USDT (TRC20)": ("TLiKyeqyp19KpBQM6hMuJoYvuaXV2tA9FF", "<:tetherusdtlogo:1183823915575943268>"),
    "Eth (Erc20)" : ("0xffecb9ad9f19e6434ddd7a390ba2c646654d5e2e" , "<:eth:1159939686983270550>"),
    "Binance to Binance & USDT" : ("581490126", "<:binancecrypto43240993591027:1187723449066586132>"),
    "LiteCoin" :("LfrhA1ZsHPczjPfdvrCFrTFmbEa1PB8Qy8" ,"<:LTC:1237498071647129693> "),
    "Ada (Cardano) BEP20" : ("0xffecb9ad9f19e6434ddd7a390ba2c646654d5e2e", "<:cardanocrypto48047104002423:1210458255411642378>")}

# Command to display payment options
@bot.command(name="pay")
async def pay(ctx):
    class PaymentView(View):
        def __init__(self, methods):
            super().__init__(timeout=None)  # Prevents the view from timing out
            for method, (address, emoji) in methods.items():
                self.add_item(Button(label=method, emoji=emoji, style=discord.ButtonStyle.primary, custom_id=method))

    async def button_callback(interaction: discord.Interaction):
        method = interaction.data["custom_id"]
        address, emoji = payment_methods_with_emojis.get(method, ("No address found.", "❓"))
        await interaction.response.send_message(
            f"{address}",
            ephemeral=False  # Set to False so everyone can see the message
        )

    view = PaymentView(payment_methods_with_emojis)
    for button in view.children:
        if isinstance(button, Button):
            button.callback = button_callback

    await ctx.send("**Please select your preferred payment method:**", view=view)

# List of JSON file paths
JSON_FILES = [
    "MegaScales.json",
    "Chambers Of Xeric.json",
    "Theatre Of Blood.json",
    "Tombs Of Amascuts.json",
    "Infernal - Quivers.json",
    "FireCapes.json",
    "Other Bosses.json",
    "God Wars Dungeon.json",
    "The Gauntlet.json",
    "Wilderness Bosses.json",
    "Desert Treasure 2 bosses.json"
]
# Emoji mapping for each JSON file
EMOJI_MAP = {
    "Chambers Of Xeric.json": "🐲 | ",  # Example: Replace with your desired emoji for this file
    "God Wars Dungeon.json": "🦅 | ",  # Example: Replace with your desired emoji for this file
    "Desert Treasure 2 Bosses.json": "🦇 | ",
    "FireCapes.json": "👹 | ",
    "The Gauntlet.json": "🐷 | ",
    "Infernal - Quivers.json": "👹 | ",
    "Theatre Of Blood.json": "🕸 | ",
    "Wilderness Bosses.json": "🦞 | ",
    "Tombs Of Amascuts.json": "🐫 | ",
    "Other Bosses.json": "🦍 | ",
    "MegaScales.json" : "🐲 | "
}
# Function to load data from a JSON file
def load_bosses_from_file(file_path):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {file_path}.")
        return []


# Function to format numbers into human-readable strings
def format_price(price):
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f}m"
    elif price >= 1_000:
        return f"{price / 1_000:.1f}k"
    else:
        return str(price)

# Function to convert price to USD
def price_to_usd(price):
    usd_rate_per_million = 0.2
    return price / 1_000_000 * usd_rate_per_million

# Log channel ID (replace this with the actual channel ID)
LOG_CHANNEL_ID = 1344237125758881792  # Replace with your channel ID

# Define the Kill Count Form Modal
class KillCountModal(Modal):
    def __init__(self, json_file, boss_name):
        super().__init__(title="Kill Count Form")
        self.json_file = json_file
        self.boss_name = boss_name

        # Add a TextInput for the kill count
        self.kill_count_input = TextInput(
            label="Enter the number of kills:",
            placeholder="Put the number of kills you want, e.g. 100",
            required=True,
            style=discord.TextStyle.short
        )
        self.add_item(self.kill_count_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            kill_count = int(self.kill_count_input.value)  # Parse the kill count from user input
            bosses = load_bosses_from_file(self.json_file)
            boss = next((b for b in bosses if b["name"] == self.boss_name), None)

            if not boss:
                await interaction.response.send_message(f"Boss `{self.boss_name}` not found.", ephemeral=True)
                return

            # Create an embed with the boss details and calculations
            embed = discord.Embed(
                title=f"**{boss['name']}**",
                description=boss.get("caption", "No description available."),
                color=discord.Color.red()
            )
            for item in boss.get("items", []):
                total_price = item["price"] * kill_count
                total_price_formatted = format_price(total_price)
                total_usd = price_to_usd(total_price)

                field_value = (f"**Price:** {format_price(item['price'])} x {kill_count} = {total_price_formatted}\n"
                               f"**Value in $:** ${total_usd:.2f}")
                embed.add_field(name=item["name"], value=field_value, inline=False)

                if "image" in item and item["image"]:
                    embed.set_thumbnail(url=item["image"])

            embed.set_footer(
            text="Anas Services",
            icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
            )  # Footer with thumbnail-style icon
            embed.set_author(name="Boss Calculator", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please provide a valid number.", ephemeral=True)

# Log the interaction (send embed to log channel)
async def log_interaction(user, selected_boss, json_file):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel is None:
        print("Log channel not found.")
        return

    # Load the bosses from the selected JSON file
    bosses = load_bosses_from_file(json_file)
    # Find the selected boss
    boss = next((b for b in bosses if b["name"] == selected_boss), None)
    
    if not boss:
        print(f"Boss {selected_boss} not found in {json_file}.")
        return

    # Create an embed to log the interaction
    embed = discord.Embed(
        title="Boss Selection Log",
        description=f"User: {user.name}#{user.discriminator} ({user.id}) selected a boss.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Selected Boss", value=selected_boss, inline=False)
    embed.add_field(name="JSON File", value=json_file, inline=False)
    embed.add_field(name="User ID", value=user.id, inline=False)

    # Check if the boss has any associated image
    if "image" in boss and boss["image"]:
        embed.set_thumbnail(url=boss["image"])

    embed.set_footer(
            text="Anas Services",
            icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
        )  # Footer with thumbnail-style icon
    embed.set_author(name="Call Logs By Omar Bot", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

    # Send the embed to the log channel
    await log_channel.send(embed=embed)


# Boss Select Dropdown (User-Specific)
class BossSelect(discord.ui.Select):
    def __init__(self, json_file):
        self.json_file = json_file
        
        # Get the emoji for the dropdown label from EMOJI_MAP
        emoji = EMOJI_MAP.get(json_file, "🔨")  # Default to 🔨 if emoji is not found
        file_name = os.path.basename(json_file).replace(".json", "")  # Remove .json extension

        # Create dropdown options with the emoji from the JSON file and the new emoji from EMOJI_MAP
        options = [
            discord.SelectOption(
                label=f"{emoji} {boss['name']}",  # The label now has the emoji from EMOJI_MAP and boss name
                description=f"Boss {boss['name']}",
                value=boss["name"],
                emoji=boss.get("emoji", "🔨")  # Emoji for the boss from the JSON file
            )
            for boss in load_bosses_from_file(json_file)
        ]
        
        # Use the JSON file's name as the placeholder
        super().__init__(placeholder=f"{emoji}{file_name}", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_boss = self.values[0]
        # Log the interaction (send the log embed)
        await log_interaction(interaction.user, selected_boss, self.json_file)
     
        # Send the modal form for the kill count
        await interaction.response.send_modal(KillCountModal(self.json_file, selected_boss))

# View for each JSON file (with no timeout)
class BossSelectView(View):
    def __init__(self, json_file):
        super().__init__(timeout=None)  # Setting timeout to None ensures the view never expires
        self.add_item(BossSelect(json_file))

# Main command to send multiple dropdowns
@bot.command()
async def start(ctx):
    # Direct URL to the banner image
    banner_url = "https://media.discordapp.net/attachments/1344265853100621914/1345088735787745474/server_banner.gif?ex=67c34701&is=67c1f581&hm=6bd57d6ec99522c7681224acf38c9efc0b5ef121f19ad42b41b226ce0db498e5&=&width=810&height=456"
    import io

    # Download and send the banner image
    async with aiohttp.ClientSession() as session:
        async with session.get(banner_url) as response:
            if response.status == 200:
                # Read image content
                banner_data = await response.read()
                await ctx.send(file=discord.File(io.BytesIO(banner_data), filename="banner.gif"))
            else:
                await ctx.send(f"Failed to fetch the banner image. HTTP Status: {response.status}")

    # Group JSON files into chunks (e.g., 3 dropdowns per message)
    chunk_size = 3  # Number of dropdowns per message
    json_file_chunks = [JSON_FILES[i:i + chunk_size] for i in range(0, len(JSON_FILES), chunk_size)]

    for chunk in json_file_chunks:
        view = View(timeout=None)  # Create a new view for each chunk

        for json_file in chunk:
            bosses = load_bosses_from_file(json_file)
            if not bosses:  # Skip JSON files with no bosses
                print(f"Skipping {json_file}: No bosses found.")
                continue
            view.add_item(BossSelect(json_file))  # Add valid dropdowns to the view

        if len(view.children) > 0:  # Send the view only if it contains dropdowns
            await ctx.send(view=view)
        else:
            print("No valid dropdowns in this chunk.")

# Example command to handle a boss name with a multiplier
@bot.command()
async def b(ctx, *, boss_name_with_multiplier: str):
    """
    This command handles boss names with spaces and optional multipliers.
    Usage: !b The Leviathan 1
    """
    # Split the input by spaces and check if the last part is a number (multiplier)
    parts = boss_name_with_multiplier.rsplit(" ", 1)
    boss_name = parts[0]
    multiplier = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

    print(f"Command !b received. Boss name: {boss_name}, Multiplier: {multiplier}")  # Debug print

    try:
        # Load bosses from all JSON files
        bosses = []
        for json_file in JSON_FILES:
            bosses.extend(load_bosses_from_file(json_file))  # Add bosses from each file to the list

        # Find the boss by name or alias in all loaded bosses
        boss = next(
            (b for b in bosses if boss_name.lower() == b["name"].lower() or boss_name.lower() in b.get("aliases", [])),
            None
        )

        if not boss:
            await ctx.send(f"Boss `{boss_name}` not found.")
            return
        
        # Create embed with calculations
        embed = discord.Embed(
            title=f"**{boss['name']}**",
            description=boss["caption"],
            color=discord.Color.red()
        )
        for item in boss["items"]:
            total_price = item["price"] * multiplier
            total_price_formatted = format_price(total_price)
            total_usd = price_to_usd(total_price)

            field_value = (f"**Price:** {format_price(item['price'])} x {multiplier} = {total_price_formatted}\n"
                           f"**Value in $:** ${total_usd:.2f}")
            embed.add_field(name=item["name"], value=field_value, inline=False)

            if "image" in item and item["image"]:
                embed.set_thumbnail(url=item["image"])

        embed.set_footer(
            text="Anas Services",
            icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
        )  # Footer with thumbnail-style icon
        embed.set_author(name="Boss Calculator", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Error: {e}")
        await ctx.send(f"An error occurred: {e}")

# Load skills JSON data
with open("skills.json", "r") as f:
    skills_data = json.load(f)

# Load XP table from JSON
with open("xp_data.json", "r") as f:
    XP_TABLE = {int(k): v for k, v in json.load(f)["xp_data"].items()}  # Ensure keys are integers

# Constants
EXCHANGE_RATE = 0.2  # 1M GP = $0.2
EMOJI_CATEGORY = {
    "gp": "<:Coins:1344508296140161087>",  # Replace with your emoji ID for GP
    "usd": "<:Tether_USDT:1344507850914791474>"  # Replace with your emoji ID for USD
}

# Helper function to chunk text into multiple parts that fit Discord's field limit
def chunk_text(text, max_length=1024):
    # Split text into chunks of max_length or smaller
    chunks = []
    while len(text) > max_length:
        split_point = text.rfind("\n", 0, max_length)  # Find the last newline within the limit
        chunks.append(text[:split_point])
        text = text[split_point + 1:]
    chunks.append(text)  # Add the remaining text as the last chunk
    return chunks

# Command to calculate skill costs
@bot.command()
async def s(ctx, skill_name: str, levels: str):
    try:
        # Parse level range
        level_start, level_end = map(int, levels.split("-"))
        if level_start < 1 or level_end > 99 or level_start >= level_end:
            await ctx.send("Invalid level range. Use `!s skill_name start-end` with levels between 1-99.")
            return

        # Find the skill by name or alias
        skill = None
        for skill_data in skills_data:
            if skill_name.lower() == skill_data["name"].lower() or skill_name.lower() in skill_data["aliases"]:
                skill = skill_data
                break

        if not skill:
            await ctx.send(f"Error: Skill '{skill_name}' not found.")
            return

        # Calculate cheapest method breakdown
        breakdown = []
        total_gp_cost = 0
        total_usd_cost = 0
        current_level = level_start

        while current_level < level_end:
            # Find the cheapest method available at the current level
            valid_methods = [method for method in skill["methods"] if method["req"] <= current_level]
            if not valid_methods:
                await ctx.send(f"No valid methods available for level {current_level}.")
                return

            cheapest_method = min(valid_methods, key=lambda m: m["gpxp"])

            # Calculate the XP required to reach the next method or the target level
            next_method_level = min(
                (method["req"] for method in skill["methods"] if method["req"] > current_level),
                default=level_end,
            )
            target_level = min(next_method_level, level_end)
            xp_to_next = XP_TABLE[target_level] - XP_TABLE[current_level]

            # Calculate costs for this segment
            gp_cost = xp_to_next * cheapest_method["gpxp"] / 1_000_000  # Convert to millions
            usd_cost = gp_cost * EXCHANGE_RATE
            total_gp_cost += gp_cost
            total_usd_cost += usd_cost

            # Add breakdown details
            breakdown.append({
                "title": cheapest_method["title"],
                "start_level": current_level,
                "end_level": target_level,
                "gp_cost": gp_cost,
                "usd_cost": usd_cost,
                "gpxp": cheapest_method["gpxp"],
            })
            
            # Update the current level
            current_level = target_level

        # Full method calculations
        additional_calculations = []
        for method in skill["methods"]:
            if method["req"] > level_start:
                continue

            # Calculate total cost for the method from level_start to level_end
            xp_required = XP_TABLE[level_end] - XP_TABLE[level_start]
            gp_cost_full = xp_required * method["gpxp"] / 1_000_000  # Convert to millions
            usd_cost_full = gp_cost_full * EXCHANGE_RATE
            additional_calculations.append({
                "title": method["title"],
                "gpxp": method["gpxp"],
                "gp_cost": gp_cost_full,
                "usd_cost": usd_cost_full,
            })

        # Add additional calculations for full methods
        # Full method calculations (showing all available methods)
        additional_text = "\n".join([
        f"**{method['title']}** (Requires level {method['req']}) {method['gpxp']}gp/xp\n"
        f"**{(XP_TABLE[level_end] - XP_TABLE[level_start]) * method['gpxp'] / 1_000_000:,.2f}M** <:Coins:1344508296140161087>\n"
        f"**${((XP_TABLE[level_end] - XP_TABLE[level_start]) * method['gpxp'] / 1_000_000) * EXCHANGE_RATE:,.2f}** <:Tether_USDT:1344507850914791474>\n"
        for method in skill["methods"]
        ])

        # Chunk the text to ensure no field exceeds 1024 characters
        chunks = chunk_text(additional_text)

        # Embed setup
        embed = discord.Embed(
            title=f"{skill['emoji']} {skill['name']} Level {level_start} to {level_end}",
            description=f"Requires {XP_TABLE[level_end] - XP_TABLE[level_start]:,} XP",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")  # Thumbnail image
        embed.set_footer(
            text="Anas Services",
            icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
        )  # Footer with thumbnail-style icon

        # Add total cost
        embed.add_field(
            name=f"Using the cheapest methods available, level {level_start} to {level_end} will cost you:",
            value=f"**{total_gp_cost:,.2f}M** <:Coins:1344508296140161087> \n"
                  f"**${total_usd_cost:,.2f}** <:Tether_USDT:1344507850914791474>",
            inline=False,
        )

        # Add breakdown of methods
        breakdown_text = "\n".join([
            f"{segment['title']} at level {segment['start_level']} "
            f"({segment['gpxp']}gp/xp = **{segment['gp_cost']:,.2f}M** <:Coins:1344508296140161087>)"
            for segment in breakdown
        ])
        embed.add_field(
            name="This will consist of the following methods:",
            value=breakdown_text,
            inline=False,
        )

        # Add optional notes
        if skill.get("caption"):
            embed.add_field(
                name="Notes",
                value=skill["caption"],
                inline=False,
            )

        # Add each chunk as a separate field in the embed
        for idx, chunk in enumerate(chunks):
         embed.add_field(
         name=f"Alternatively, if you want to choose a specific method (Part {idx + 1}):",
         value=chunk,
         inline=False,
         )

        # Send the embed
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"Error calculating skill: {e}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()  # Sync all slash commands
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Flask setup for keeping the bot alive (Replit hosting)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = Thread(target=run)
    thread.start()

# Add restart command for the bot (Owner-only)
@bot.command()
@commands.is_owner()
async def restart(ctx):
    await ctx.send("Restarting bot...")
    os.execv(__file__, ['python'] + os.sys.argv)

# Retrieve the token from the environment variable
token = os.getenv('DISCORD_BOT_TOKEN')
if not token:
    print("Error: DISCORD_BOT_TOKEN is not set in the environment variables.")
    exit(1)

# Keep the bot alive for Replit hosting
keep_alive()

@bot.command()
async def test(ctx):
    await ctx.send("Bot is responding!")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")
# Run the bot with the token
bot.run(token)
