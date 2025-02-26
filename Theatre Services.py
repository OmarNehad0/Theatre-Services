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



