import discord
from discord.ext import commands, tasks
import os
from flask import Flask
from threading import Thread
import logging
from discord import app_commands
import json
import random
import asyncio
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import io
import math
import time
import discord
from discord.ext import commands
import aiohttp
from discord.ui import View, Button, Modal, TextInput
import pymongo
import gspread
from discord import Embed, Interaction
from pymongo import MongoClient, ReturnDocument
from collections import defaultdict
import re
import difflib

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.members = True

# Create bot instance with intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Connect to MongoDB using the provided URI from Railway
mongo_uri = os.getenv("MONGO_URI")  # You should set this in your Railway environment variables
client = MongoClient(mongo_uri)

# Choose your database
db = client['MongoDB']  # Replace with the name of your database

# Access collections (equivalent to Firestore collections)
wallets_collection = db['wallets']
orders_collection = db['orders']
counters_collection = db["order_counters"]  # New collection to track order ID

# The fixed orders posting channel
ORDERS_CHANNEL_ID = 1344132518680465428

# Allowed roles for commands
ALLOWED_ROLES = {1343638466621345905, 1343638967618375691, 1343639083402002546}

def has_permission(user: discord.Member):
    return any(role.id in ALLOWED_ROLES for role in user.roles)

async def log_command(interaction: discord.Interaction, command_name: str, details: str):
    # Mapping of servers to their respective log channels
    LOG_CHANNELS = {
        1343444130986201118: 1344237125758881792
    }

    for guild_id, channel_id in LOG_CHANNELS.items():
        log_guild = interaction.client.get_guild(guild_id)  # Get the guild
        if log_guild:
            log_channel = log_guild.get_channel(channel_id)  # Get the log channel
            if log_channel:
                embed = discord.Embed(title="📜 Command Log", color=discord.Color.red())
                embed.add_field(name="👤 User", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                embed.add_field(name="💻 Command", value=command_name, inline=False)
                embed.add_field(name="📜 Details", value=details, inline=False)
                embed.set_footer(text=f"Used in: {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
                await log_channel.send(embed=embed)
            else:
                print(f"⚠️ Log channel not found in {log_guild.name} ({channel_id})")
        else:
            print(f"⚠️ Log guild not found: {guild_id}")

# Syncing command tree for slash commands
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

def get_wallet(user_id):
    # Attempt to fetch the user's wallet data from MongoDB
    wallet_data = wallets_collection.find_one({"user_id": user_id})

    # If the wallet doesn't exist in the database, create a new one with default values
    if not wallet_data:
        print(f"Wallet not found for {user_id}, creating new wallet...")
        wallet_data = {
            "user_id": user_id,
            "wallet": 0,    # Initialize with 0M
            "spent": 0,     # Initialize with 0M
            "deposit": 0    # Initialize with 0M
        }
        # Insert the new wallet into the database
        wallets_collection.insert_one(wallet_data)
        print(f"New wallet created for {user_id}: {wallet_data}")

    return wallet_data



# Function to update wallet in MongoDB
def update_wallet(user_id, field, value):
    # Make sure the wallet document exists before updating
    wallet_data = get_wallet(user_id)
    
    # If the wallet does not contain the required field, we initialize it with the correct value
    if field not in wallet_data:
        wallet_data[field] = 0  # Initialize the field if missing
    
    # Update wallet data by incrementing the field value
    wallets_collection.update_one(
        {"user_id": user_id},
        {"$inc": {field: value}},  # Increment the field (e.g., wallet, deposit, spent)
        upsert=True  # Insert a new document if one doesn't exist
    )


@bot.tree.command(name="wallet", description="Check a user's wallet balance")
async def wallet(interaction: discord.Interaction, user: discord.Member = None):
    # Define role IDs
    self_only_roles = {1345120948885389443,1343638843659653190}
    allowed_roles = {1343638466621345905, 1343638967618375691, 1343639083402002546}

    # Check if user has permission
    user_roles = {role.id for role in interaction.user.roles}
    has_self_only_role = bool(self_only_roles & user_roles)  # User has at least one self-only role
    has_allowed_role = bool(allowed_roles & user_roles)  # User has at least one allowed role

    # If user has no valid role, deny access
    if not has_self_only_role and not has_allowed_role:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    # If user has only a self-only role (and not an allowed role), force them to check their own wallet
    if has_self_only_role and not has_allowed_role:
        user = interaction.user  

    # Default to interaction user if no target user is specified
    if user is None:
        user = interaction.user

    # Fetch wallet data
    user_id = str(user.id)
    wallet_data = get_wallet(user_id)
    
    # Default missing fields to 0
    deposit_value = wallet_data.get('deposit', 0)
    wallet_value = wallet_data.get('wallet', 0)
    spent_value = wallet_data.get('spent', 0)

    # Get user's avatar (fallback to default image)
    default_thumbnail = "https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
    thumbnail_url = user.avatar.url if user.avatar else default_thumbnail

    # Create embed message
    embed = discord.Embed(title=f"{user.display_name}'s Wallet 💳", color=discord.Color.blue())
    embed.set_thumbnail(url=thumbnail_url)
    embed.add_field(name="📥 Deposit", value=f"```💵 {deposit_value}M```", inline=False)
    embed.add_field(name="💰 Wallet", value=f"```💰 {wallet_value}M```", inline=False)
    embed.add_field(name="💸 Spent", value=f"```🛍️ {spent_value}M```", inline=False)
    embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&=")

    # Ensure requester avatar exists
    requester_avatar = interaction.user.avatar.url if interaction.user.avatar else default_thumbnail
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=requester_avatar)

    await interaction.response.send_message(embed=embed)




@bot.tree.command(name="wallet_add_remove", description="Add or remove value from a user's wallet")
@app_commands.choices(action=[
    discord.app_commands.Choice(name="Add", value="add"),
    discord.app_commands.Choice(name="Remove", value="remove")
])
async def wallet_add_remove(
    interaction: discord.Interaction,
    user: discord.Member,
    action: discord.app_commands.Choice[str],
    value: float
):  
    if not has_permission(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return

    user_id = str(user.id)
    wallet_data = get_wallet(user_id) or {"wallet": 0, "deposit": 0, "spent": 0}

    if action.value == "remove":
        update_wallet(user_id, "wallet", -value)
    else:
        update_wallet(user_id, "wallet", value)

    updated_wallet = get_wallet(user_id) or {"wallet": 0, "deposit": 0, "spent": 0}
    wallet_value = updated_wallet.get("wallet", 0)
    deposit_value = updated_wallet.get("deposit", 0)
    spent_value = updated_wallet.get("spent", 0)

    embed = discord.Embed(title=f"{user.display_name}'s Wallet 💳", color=discord.Color.blue())
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="📥 Deposit", value=f"```💵 {deposit_value:,}M```", inline=False)
    embed.add_field(name="💰 Wallet", value=f"```💰 {wallet_value:,}M```", inline=False)
    embed.add_field(name="💸 Spent", value=f"```🛍️ {spent_value:,}M```", inline=False)
    embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&=")
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
    
    await interaction.response.send_message(f"✅ {action.name}ed {value:,}M.", embed=embed)
    await log_command(interaction, "wallet_add_remove", f"User: {user.mention} | Action: {action.name} | Value: {value:,}M")


@bot.tree.command(name="deposit", description="Set or remove a user's deposit value")
@app_commands.choices(action=[
    discord.app_commands.Choice(name="Set", value="set"),
    discord.app_commands.Choice(name="Remove", value="remove")
])
async def deposit(interaction: discord.Interaction, user: discord.Member, action: str, value: int):
    if not has_permission(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    user_id = str(user.id)
    
    # Fetch current wallet data
    wallet_data = get_wallet(user_id)

    # Ensure the deposit field exists
    current_deposit = wallet_data.get("deposit", 0)

    if action == "set":
        new_deposit = current_deposit + value  # Add the deposit value
    elif action == "remove":
        if value > current_deposit:
            await interaction.response.send_message(f"⚠ Cannot remove {value}M. The user only has {current_deposit}M in deposit.", ephemeral=True)
            return
        new_deposit = current_deposit - value  # Subtract the deposit value

    # Update deposit value in MongoDB
    update_wallet(user_id, "deposit", new_deposit - current_deposit)

    # Fetch updated wallet data
    updated_wallet = get_wallet(user_id)

    # Format values
    deposit_value = f"```💵 {updated_wallet['deposit']:,}M```"
    wallet_value = f"```💰 {updated_wallet['wallet']:,}M```"
    spent_value = f"```🛍️ {updated_wallet['spent']:,}M```"

    # Create an embed
    embed = discord.Embed(title=f"{user.display_name}'s Wallet 💳", color=discord.Color.blue())
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="📥 Deposit", value=deposit_value, inline=False)
    embed.add_field(name="💰 Wallet", value=wallet_value, inline=False)
    embed.add_field(name="💸 Spent", value=spent_value, inline=False)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
    embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&=")
    # Send response
    await interaction.response.send_message(f"✅ {action.capitalize()}ed deposit value for {user.name} by {value:,}M.", embed=embed)
    await log_command(interaction, "Deposit Set/Remove", f"User: {user.mention} (`{user.id}`)\nAction: {action.capitalize()}\nAmount: {value:,}M")

class OrderButton(View):
    def __init__(self, order_id, deposit_required, customer_id, original_channel_id, message_id, post_channel_id):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.deposit_required = deposit_required
        self.customer_id = customer_id
        self.original_channel_id = original_channel_id  # Channel where /post was used
        self.message_id = message_id
        self.post_channel_id = post_channel_id  # Channel where order is posted

    @discord.ui.button(label="✅ Accept TOS & Job", style=discord.ButtonStyle.primary)
    async def accept_job(self, interaction: Interaction, button: discord.ui.Button):
        order = orders_collection.find_one({"_id": self.order_id})
        if not order:
            await interaction.response.send_message("Order not found!", ephemeral=True)
            return

        if order.get("worker"):
            await interaction.response.send_message("This order has already been claimed!", ephemeral=True)
            return

        user_wallet = get_wallet(str(interaction.user.id))
        if user_wallet.get("deposit", 0) < self.deposit_required:
            await interaction.response.send_message("You do not have enough deposit to claim this order!", ephemeral=True)
            return

        # Assign worker
        orders_collection.update_one({"_id": self.order_id}, {"$set": {"worker": interaction.user.id}})

        # Delete the original order post from the posting channel
        post_channel = bot.get_channel(self.post_channel_id)
        if post_channel:
            try:
                message = await post_channel.fetch_message(self.message_id)
                await message.delete()
            except:
                pass

        # Grant worker access to the original /post channel (not the posting channel)
        original_channel = bot.get_channel(self.original_channel_id)
        if original_channel:
            await original_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)

            # ✅ Send "Order Claimed" message only in the `/post` channel
            value = order["value"]
            embed = discord.Embed(title="🎡 Order Claimed", color=discord.Color.green())
            embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
            embed.set_author(name="👑 Anas System", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
            embed.add_field(name="Description", value=order.get("description", "No description provided."), inline=False)
            embed.add_field(name="👷 Worker", value=interaction.user.mention, inline=True)
            embed.add_field(name="📌 Customer", value=f"<@{self.customer_id}>", inline=True)
            embed.add_field(name="💰 Deposit Required", value=f"```{self.deposit_required}M```", inline=True)
            embed.add_field(name="💵 Order Value", value=f"```{value}M```", inline=True)
            embed.add_field(name="🆔 Order ID", value=self.order_id, inline=True)
            embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&=")
            embed.set_footer(text="Anas System", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
            
            await original_channel.send(embed=embed)  # ✅ Send embed only in `/post` channel

            # ✅ Send message to `/post` channel pinging the worker & customer
            claim_message = f"**hello! <@{self.customer_id}>, <@{interaction.user.id}> is your worker for this job. You can put info for him using `!inf`**"
            await original_channel.send(claim_message)

        await interaction.response.send_message("Order claimed successfully!", ephemeral=True)



@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    # Reload buttons for active orders
    for order in orders_collection.find({"worker": None}):  # Only for unclaimed orders
        channel = bot.get_channel(order["channel_id"])
        if channel:
            try:
                message = await channel.fetch_message(order["message_id"])
                view = OrderButton(order["_id"], order["deposit_required"], order["customer"], order["original_channel_id"], order["message_id"])
                await message.edit(view=view)
            except discord.NotFound:
                print(f"Order message {order['message_id']} not found, skipping.")
    
    print("Re-registered all active order buttons!")

def get_next_order_id():
    counter = counters_collection.find_one({"_id": "order_counter"})
    
    if not counter:
        # Initialize the counter to 46 if it does not exist
        counters_collection.insert_one({"_id": "order_counter", "seq": 46})
        return 46  # First order ID should be 46

    # Increment and return the next order ID
    counter = counters_collection.find_one_and_update(
        {"_id": "order_counter"},
        {"$inc": {"seq": 1}},  # Increment the existing counter
        return_document=ReturnDocument.AFTER
    )
    return counter["seq"]

@bot.tree.command(name="post", description="Post a new order.")
@app_commands.describe(
    customer="The customer for the order",
    value="The value of the order (in millions)",
    deposit_required="The deposit required for the order",
    holder="The holder of the order",
    channel="The channel to post the order (mention or ID)",
    description="Description of the order"
)
async def post(interaction: discord.Interaction, customer: discord.Member, value: int, deposit_required: int, holder: discord.Member, channel: discord.TextChannel, description: str):
    if not has_permission(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    channel_id = channel.id
    order_id = get_next_order_id()
    post_channel_id = interaction.channel.id  # Store the channel where /post was used


    # Define role IDs
    role1_id = 1343638843659653190
    role2_id = 1343639083402002546

    # Check if roles exist in the guild
    role1 = discord.utils.get(interaction.guild.roles, id=role1_id)
    role2 = discord.utils.get(interaction.guild.roles, id=role2_id)

    # Determine which role to ping
    if role1:
        role_ping = role1.mention
    elif role2:
        role_ping = role2.mention
    else:
        role_ping = None  # No roles found, so no ping
    embed = discord.Embed(color=0xffa500)
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
    embed.set_author(name="🎭 New Order Posted", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="💵 Value", value=f"```{value}M```", inline=True)
    embed.add_field(name="💰 Deposit Required", value=f"```{deposit_required}M```", inline=True)
    embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&=")
    embed.set_footer(text=f"Order ID: {order_id}", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")

    channel_to_post = interaction.guild.get_channel(channel_id)
    if channel_to_post:
        # Send message with role ping if a role exists
        if role_ping:
            message = await channel_to_post.send(f"{role_ping}", embed=embed)
        else:
            message = await channel_to_post.send(embed=embed)

        # Add order button functionality
        await message.edit(view=OrderButton(order_id, deposit_required, customer.id, post_channel_id, message.id, channel_id))

        orders_collection.insert_one({
            "_id": order_id,
            "customer": customer.id,
            "posted_by": interaction.user.id,
            "worker": None,
            "value": value,
            "deposit_required": deposit_required,
            "holder": holder.id,
            "message_id": message.id,
            "channel_id": channel.id,
            "original_channel_id": post_channel_id,  # Store where /post was used
            "description": description
        })

        confirmation_embed = embed.copy()
        await interaction.channel.send(embed=confirmation_embed)
        await interaction.response.send_message("Order posted successfully!", ephemeral=True)
        await log_command(interaction, "Order Posted", f"Customer: {customer.mention} (`{customer.id}`)\nValue: {value:,}M\nDeposit Required: {deposit_required:,}M\nHolder: {holder.mention} (`{holder.id}`)\nChannel: {channel.mention}\nDescription: {description}")
    else:
        await interaction.response.send_message("Invalid channel specified.", ephemeral=True)

@bot.tree.command(name="set", description="Set an order directly with worker.")
async def set_order(interaction: Interaction, customer: discord.Member, value: int, deposit_required: int, holder: discord.Member, description: str, worker: discord.Member):
    if not has_permission(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    order_id = get_next_order_id()  # Get a unique order ID
    original_channel_id = interaction.channel.id  # Save the original posting channel
    
    embed = Embed(title="Order Set", color=0x0000FF)
    embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
    embed.set_author(name="🛠️ Order Set", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="📌 Customer", value=customer.mention, inline=True)
    embed.add_field(name="💵 Value", value=f"```{value}M```", inline=True)
    embed.add_field(name="💰 Deposit Required", value=f"```{deposit_required}M```", inline=True)
    embed.add_field(name="🔐 Holder", value=holder.mention, inline=True)
    embed.add_field(name="👷 Worker", value=worker.mention, inline=True)
    embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&=")
    embed.set_footer(text=f"Order ID: {order_id}", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&=")
    
    # Send the order to the channel where the command was used
    original_channel = bot.get_channel(original_channel_id)
    if original_channel:
        message = await original_channel.send(embed=embed)  # Send the message to the original channel
        message_id = message.id  # Retrieve the message ID
    
    # Store order in the database, including the original channel where the order was posted
    orders_collection.insert_one({
        "_id": order_id,  # Use unique order ID
        "customer": customer.id,
        "posted_by": interaction.user.id,
        "worker": worker.id,  # Directly assign worker
        "value": value,
        "deposit_required": deposit_required,
        "holder": holder.id,
        "message_id": message_id,
        "channel_id": original_channel.id,  # Store the original channel ID
        "original_channel_id": original_channel_id,  # Store the original channel ID
        "description": description
    })

    # Notify the user that the order was successfully set
    await interaction.response.send_message(f"Order set with Worker {worker.mention}!", ephemeral=True)
    await log_command(interaction, "Order Set", f"Customer: {customer.mention} (`{customer.id}`)\nWorker: {worker.mention} (`{worker.id}`)\nValue: {value:,}M\nDeposit Required: {deposit_required:,}M\nHolder: {holder.mention} (`{holder.id}`)\nDescription: {description}")

    # Now, add the worker to the original channel and grant permissions
    if original_channel:
        try:
            # Add the worker to the channel, allowing them to read and send messages
            await original_channel.set_permissions(worker, read_messages=True, send_messages=True)
            print(f"Permissions granted to {worker.name} in {original_channel.name}.")
        except Exception as e:
            print(f"Failed to set permissions for {worker.name} in {original_channel.name}: {e}")
@bot.tree.command(name="complete", description="Mark an order as completed.")
async def complete(interaction: Interaction, order_id: int):
    if not has_permission(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    order = orders_collection.find_one({"_id": order_id})
    if not order:
        await interaction.response.send_message("Order not found!", ephemeral=True)
        return

    if order.get("status") == "completed":
        await interaction.response.send_message("⚠️ This order has already been marked as completed.", ephemeral=True)
        return

    # Transfer funds
    update_wallet(str(order["customer"]), "spent", order["value"])
    
    total_value = order["value"]
    worker_payment = round(total_value * 0.80, 1)
    commission_value = round(total_value * 0.15, 1)
    helper_payment = round(total_value * 0.05, 1)

    update_wallet(str(order["worker"]), "wallet", float(worker_payment))
    update_wallet("server", "commission", float(commission_value))
    update_wallet(str(order.get("posted_by", interaction.user.id)), "wallet", float(helper_payment))

    orders_collection.update_one({"_id": order_id}, {"$set": {"status": "completed"}})

    # Notify the original channel
    original_channel = bot.get_channel(order["original_channel_id"])
    if original_channel:
        embed = Embed(title="✅ Order Completed", color=discord.Color.blue())
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif")
        embed.set_author(name="Anas System", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif")
        embed.add_field(name="Description", value=order.get("description", "No description provided."), inline=False)
        embed.add_field(name="👷 Worker", value=f"<@{order['worker']}>", inline=True)
        embed.add_field(name="📌 Customer", value=f"<@{order['customer']}>", inline=True)
        embed.add_field(name="💰 Value", value=f"```{total_value}M```", inline=True)
        embed.add_field(name="💵 Worker Payment", value=f"```{worker_payment}M```", inline=True)
        embed.add_field(name="📦 Server Commission", value=f"```{commission_value}M```", inline=True)
        embed.add_field(name="📬 Helper Reward", value=f"```{helper_payment}M```", inline=True)
        embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif")
        embed.set_footer(text=f"Order ID: {order_id}", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif")
        await original_channel.send(embed=embed)

    # DM the worker
    worker = bot.get_user(order["worker"])
    if worker:
        dm_embed = Embed(title="✅ Order Completed", color=discord.Color.blue())
        dm_embed.set_thumbnail(url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif")
        dm_embed.set_author(name="Anas System", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif")
        dm_embed.add_field(name="Description", value=order.get("description", "No description provided."), inline=False)
        dm_embed.add_field(name="📌 Customer", value=f"<@{order['customer']}>", inline=True)
        dm_embed.add_field(name="💰 Value", value=f"```{total_value}M```", inline=True)
        dm_embed.add_field(name="💵 Your Payment", value=f"```{worker_payment}M```", inline=True)
        dm_embed.set_image(url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif")
        dm_embed.set_footer(text=f"Order ID: {order_id}", icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif")
        await worker.send(embed=dm_embed)

    await interaction.response.send_message("Order marked as completed!", ephemeral=True)
    await log_command(interaction, "Order Completed", (
        f"Order ID: {order_id}\nMarked by: {interaction.user.mention} (`{interaction.user.id}`)\n"
        f"Worker: <@{order['worker']}> (`{order['worker']}`)\n"
        f"Customer: <@{order['customer']}> (`{order['customer']}`)\n"
        f"Value: {total_value}M\nWorker Payment: {worker_payment}M\n"
        f"Server Commission: {commission_value}M\nHelper Reward: {helper_payment}M"
    ))

# 📌 /order_deletion command
@bot.tree.command(name="order_deletion", description="Delete an order.")
async def order_deletion(interaction: Interaction, order_id: int):
    if not has_permission(interaction.user):
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    order = orders_collection.find_one({"_id": order_id})
    
    if not order:
        await interaction.response.send_message("❌ Order not found!", ephemeral=True)
        return

    # Delete the order message in the orders channel
    order_channel = bot.get_channel(order["channel_id"])
    if order_channel:
        try:
            message = await order_channel.fetch_message(order["message_id"])
            await message.delete()
        except discord.NotFound:
            print(f"⚠️ Message for order {order_id} not found in orders channel. Skipping deletion.")

    # Delete the original post message in the interaction channel
    original_channel = bot.get_channel(order["original_channel_id"])
    if original_channel:
        try:
            original_message = await original_channel.fetch_message(order["message_id"])
            await original_message.delete()
        except discord.NotFound:
            print(f"⚠️ Original message for order {order_id} not found. Skipping deletion.")

    # Remove the order from MongoDB
    orders_collection.delete_one({"_id": order_id})
    
    await interaction.response.send_message(f"✅ Order {order_id} has been successfully deleted.", ephemeral=True)
    await log_command(interaction, "Order Deleted", f"Order ID: {order_id}\nDeleted by: {interaction.user.mention} (`{interaction.user.id}`)")

@bot.tree.command(name="view_order", description="View details of an order")
async def view_order(interaction: discord.Interaction, order_id: int):
    # Required role IDs
    allowed_roles = {1343638466621345905, 1343638967618375691, 1343639083402002546}

    # Check if user has at least one of the required roles
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    order = orders_collection.find_one({"_id": order_id})
    
    if not order:
        await interaction.response.send_message("❌ Order not found.", ephemeral=True)
        return

    # Extract values safely, handling possible None values
    worker_id = order.get("worker", {}).get("low") if isinstance(order.get("worker"), dict) else order.get("worker", "Not Assigned")
    customer_id = order.get("customer", {}).get("low") if isinstance(order.get("customer"), dict) else order.get("customer", "Unknown")
    holder_id = order.get("holder", {}).get("low") if isinstance(order.get("holder"), dict) else order.get("holder", "N/A")
    
    deposit = order.get("deposit_required", 0)
    value = order.get("value", 0)
    description = order.get("description", "No description provided")

    # Get status, default to "In Progress"
    status = order.get("status", "In Progress").capitalize()

    embed = discord.Embed(title="📦 Order Details", color=discord.Color.green())
    embed.add_field(name="🎮 Status", value=status, inline=False)
    embed.add_field(name="👷 Worker", value=f"<@{worker_id}>" if isinstance(worker_id, int) else worker_id, inline=False)
    embed.add_field(name="📌 Customer", value=f"<@{customer_id}>" if isinstance(customer_id, int) else customer_id, inline=False)
    embed.add_field(name="🔐 Holder", value=f"<@{holder_id}>" if isinstance(holder_id, int) else holder_id, inline=False)
    embed.add_field(name="Description", value=description, inline=False)
    embed.add_field(name="💰 Deposit", value=f"```{deposit}M```", inline=True)
    embed.add_field(name="💵 Order Value", value=f"```{value}M```", inline=True)
    embed.add_field(name="🆔 Order ID", value=order_id, inline=False)

    await interaction.response.send_message(embed=embed)

# Syncing command tree for slash commands
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Define the constants
EXCHANGE_RATE = 0.2  # 1M GP = $0.2
EMOJI_CATEGORY = {
    "gp": "<:Coins:1344508296140161087> ",  # Replace with your emoji ID for GP
    "usd": "<:Tether_USDT:1344507850914791474>"  # Replace with your emoji ID for USD
}

# Load quest data from JSON file
with open("quests-members.json", "r") as f:
    quest_data = json.load(f)

# Normalization function to clean input
def normalize(text):
    return re.sub(r"[^\w\s]", "", text.lower()).strip()

# Helper function to find a quest by name or alias (with fuzzy matching)
def find_quest(quest_name):
    normalized_input = normalize(quest_name)

    all_names = []
    name_map = {}

    for quest in quest_data:
        normalized_name = normalize(quest["name"])
        all_names.append(normalized_name)
        name_map[normalized_name] = quest

        for alias in quest.get("aliases", []):
            normalized_alias = normalize(alias)
            all_names.append(normalized_alias)
            name_map[normalized_alias] = quest

        if normalized_input == normalized_name or normalized_input in [normalize(a) for a in quest.get("aliases", [])]:
            return quest, None

    # Fuzzy match
    close_matches = difflib.get_close_matches(normalized_input, all_names, n=1, cutoff=0.6)
    if close_matches:
        best_match = close_matches[0]
        return name_map[best_match], best_match

    return None, None

# Dummy price-to-USD conversion function
def price_to_usd(gp_amount):
    exchange_rate = 0.70 / 1000000  # 0.70 USD per 1m GP
    return gp_amount * exchange_rate

# Quest calculator command
@bot.command(name="q")
async def quest_calculator(ctx, *, quests: str):
    quest_names = [q.strip() for q in quests.split(",")]
    found_quests = []
    not_found_quests = []
    total_price_gp = 0

    for quest_name in quest_names:
        quest, matched_name = find_quest(quest_name)
        if quest:
            price_m = quest['price'] // 1000000
            found_quests.append(f"• **{quest['name']}**: {price_m}M {EMOJI_CATEGORY['gp']}")
            total_price_gp += quest["price"]
        else:
            # Try to suggest a similar name
            suggestion, _ = find_quest(quest_name)
            if suggestion:
                not_found_quests.append(f"• `{quest_name}` not found. Did you mean **{suggestion['name']}**?")
            else:
                not_found_quests.append(f"• `{quest_name}` not found.")

    total_price_usd = price_to_usd(total_price_gp)

    embed = discord.Embed(
        title="<:260pxQuests:1375438815144968292> Quest Calculator <a:purple_fire:1353597568776671283>",
        color=discord.Color.purple()
    )
    embed.set_footer(
        text="Anas Services",
        icon_url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
    )
    embed.set_thumbnail(
        url="https://media.discordapp.net/attachments/1344265853100621914/1345088681924366406/avatar.gif?ex=67c346f4&is=67c1f574&hm=d84730a5eb8bd1b0a33d5d8783bef2faa3492f9f0fdce089ff79e7248d357e9b&="
    )

    if found_quests:
        embed.add_field(name="<:260pxQuests:1375438815144968292> Found Quests", value="\n".join(found_quests), inline=False)

    if total_price_gp > 0:
        embed.add_field(
            name="Order Total",
            value=(
                f"{total_price_gp // 1000000}M {EMOJI_CATEGORY['gp']}\n"
                f"${total_price_usd:.2f} {EMOJI_CATEGORY['usd']}"
            ),
            inline=False
        )

    if not_found_quests:
        embed.add_field(
            name="Could not find the following quests",
            value="\n".join(not_found_quests),
            inline=False
        )

    embed.set_image(
        url="https://media.discordapp.net/attachments/1344265853100621914/1345117130403610696/banner.gif?ex=67c36172&is=67c20ff2&hm=5d727bb56b2eb2f48b46bc56efc9f0ab185303a870b74e463dd563a73f4c269c&="
    )

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
        description="**We Appreciate Vouching For Us On [Sythe](https://www.sythe.org/threads/anas-services-vouch-thread/).**\n\n**Please select your rating below (1-5 stars).**\nOnce selected, you will be asked to leave a review."
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
    "Chambers Of Xeric.json",
    "Theatre Of Blood.json",
    "Tombs Of Amascuts.json",
    "Infernal - Quivers.json",
    "FireCapes.json",
    "Other Bosses.json",
    "God Wars Dungeon.json",
    "The Gauntlet.json",
    "Wilderness Bosses.json",
    "Desert Treasure 2 Bosses.json"
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
    "Other Bosses.json": "🦍 | "
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
    banner_url = "https://media.discordapp.net/attachments/1344140486188994590/1375442768033484900/banner.gif?ex=68345766&is=683305e6&hm=4c4c7e17334a6ff69d820afb56e563a8feda13fc58cf778f03a482e3389157d5&="
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
        embed.add_field(name="**Start Level**", value=f"**```{level_start}```**", inline=True)
        embed.add_field(name="**End Level**", value=f"**```{level_end}```**", inline=True)
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
        embed.add_field(
            name="__Alternatively, if you want to choose a specific method__",
            value=chunks[0],
            inline=False,
        )

        for chunk in chunks[1:]:
           embed.add_field(
           name="",
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
