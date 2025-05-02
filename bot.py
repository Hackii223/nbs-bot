import discord
from discord.ext import commands
import json
import os
import re
from datetime import datetime, timedelta
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

PARTNER_CHANNEL_ID = 1363982747361611847
PUNKTY_FILE = "punkty.json"
PARTNER_LOG_FILE = "partner_log.json"
PARTNERSTWA_FILE = "partnerstwa.json"

GUILD_ID = 1345405580482969682  # <-- Twój serwer ID

if os.path.exists(PUNKTY_FILE):
    with open(PUNKTY_FILE, "r") as f:
        punkty_data = json.load(f)
else:
    punkty_data = {}

if os.path.exists(PARTNER_LOG_FILE):
    with open(PARTNER_LOG_FILE, "r") as f:
        partner_log = json.load(f)
else:
    partner_log = {}

def dodaj_punkt(user_id):
    uid = str(user_id)
    punkty_data[uid] = punkty_data.get(uid, 0) + 1
    with open(PUNKTY_FILE, "w") as f:
        json.dump(punkty_data, f)

def pobierz_punkty(user_id):
    return punkty_data.get(str(user_id), 0)

def zapis_partnerstwa(link, user_id, partner_mention):
    partner_log[link] = datetime.now().isoformat()
    with open(PARTNER_LOG_FILE, "w") as f:
        json.dump(partner_log, f)

    nowe = {
        "user_id": str(user_id),
        "partner": partner_mention,
        "link": link,
        "timestamp": datetime.now().isoformat()
    }

    if os.path.exists(PARTNERSTWA_FILE):
        with open(PARTNERSTWA_FILE, "r") as f:
            historia = json.load(f)
    else:
        historia = []

    historia.append(nowe)
    with open(PARTNERSTWA_FILE, "w") as f:
        json.dump(historia, f, indent=2)

def czy_niedozwolony_link(link):
    if link in partner_log:
        ostatnie = datetime.fromisoformat(partner_log[link])
        return datetime.now() - ostatnie < timedelta(days=3)
    return False

def czy_limit_partnerstw(user_id, partner_mention):
    if not os.path.exists(PARTNERSTWA_FILE):
        return False

    with open(PARTNERSTWA_FILE, "r") as f:
        historia = json.load(f)

    teraz = datetime.now()
    licznik = 0

    for p in historia:
        if (
            p["user_id"] == str(user_id)
            and p["partner"] == partner_mention
            and datetime.fromisoformat(p["timestamp"]) > teraz - timedelta(days=3)
        ):
            licznik += 1

    return licznik >= 3

@bot.event
async def on_ready():
    print(f"✅ Bot działa poprawnie! Zalogowano jako {bot.user}")
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"🔁 Zsynchronizowano {len(synced)} komend na serwerze {GUILD_ID}.")
    except Exception as e:
        print(f"❌ Błąd synchronizacji: {e}")

    bot.loop.create_task(stay_alive())

@bot.event
async def on_message(message):
    try:
        if message.author.bot or message.channel.id != PARTNER_CHANNEL_ID:
            return

        link_match = re.search(r"(https://)?(discord\.gg|discord\.com/invite)/[^\s]+", message.content)

        if link_match and message.mentions:
            link = link_match.group()
            wykonawca = message.author
            partner_user = message.mentions[0]

            if czy_niedozwolony_link(link):
                await message.channel.send("⛔ Ktoś zawarł partnerstwo z tym serwerem w ciągu ostatnich 3 dni.")
                return

            if czy_limit_partnerstw(wykonawca.id, partner_user.mention):
                await message.channel.send("⛔ Z tym partnerem wykonano już 3 partnerstwa w ciągu ostatnich 3 dni.")
                return

            zapis_partnerstwa(link, wykonawca.id, partner_user.mention)
            dodaj_punkt(wykonawca.id)
            punkty = pobierz_punkty(wykonawca.id)

            embed = discord.Embed(
                title="✅ Dobrze wykonane partnerstwo",
                description=f"🔗 Link: {link}\n👤 Partner: {partner_user.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Punkty użytkownika", value=str(punkty))
            embed.set_footer(text=f"Wykonane przez: {wykonawca}")
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("❌ Wiadomość musi zawierać link do serwera i oznaczenie partnera!")

    except Exception as e:
        print(f"❌ Błąd w on_message: {e}")

    await bot.process_commands(message)

@bot.tree.command(name="punkty", description="Sprawdź swoje punkty partnerstw", guild=discord.Object(id=GUILD_ID))
async def punkty(interaction: discord.Interaction):
    user_points = pobierz_punkty(interaction.user.id)
    await interaction.response.send_message(f"🔢 Masz {user_points} punktów partnerstw.", ephemeral=True)

@bot.tree.command(name="resetpunkty", description="Zresetuj punkty partnerstw użytkownika (admin only)", guild=discord.Object(id=GUILD_ID))
@discord.app_commands.describe(użytkownik="Użytkownik, którego punkty chcesz zresetować")
async def resetpunkty(interaction: discord.Interaction, użytkownik: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⛔ Nie masz uprawnień do tej komendy.", ephemeral=True)
        return

    punkty_data[str(użytkownik.id)] = 0
    with open(PUNKTY_FILE, "w") as f:
        json.dump(punkty_data, f)

    await interaction.response.send_message(f"✅ Punkty użytkownika {użytkownik.mention} zostały zresetowane.")

@bot.tree.command(name="partnerstwa", description="Zobacz historię partnerstw danego użytkownika", guild=discord.Object(id=GUILD_ID))
@discord.app_commands.describe(użytkownik="Użytkownik, którego partnerstwa chcesz zobaczyć")
async def partnerstwa(interaction: discord.Interaction, użytkownik: discord.Member):
    if not os.path.exists(PARTNERSTWA_FILE):
        await interaction.response.send_message("📄 Brak historii partnerstw.", ephemeral=True)
        return

    with open(PARTNERSTWA_FILE, "r") as f:
        historia = json.load(f)

    partnerstwa_uzytkownika = [p for p in historia if p["user_id"] == str(użytkownik.id)]

    if not partnerstwa_uzytkownika:
        await interaction.response.send_message(f"🔍 {użytkownik.mention} nie ma jeszcze żadnych partnerstw.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📘 Partnerstwa użytkownika {użytkownik.name}",
        color=discord.Color.blurple()
    )

    for i, p in enumerate(partnerstwa_uzytkownika[-5:], 1):
        embed.add_field(
            name=f"Partnerstwo {i}",
            value=f"🔗 {p['link']}\n👤 {p['partner']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

async def stay_alive():
    while True:
        await asyncio.sleep(5)
        print("✅ Bot ciągle działa!")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
