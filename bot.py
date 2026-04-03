import discord
import os
import io
import time
import requests
from collections import defaultdict
from groq import Groq

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
REPLICATE_API_KEY = os.getenv("REPLICATE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq client for chat
client = Groq(api_key=GROQ_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

user_memory = defaultdict(list)
personalities = {
    "default": "You are a helpful and friendly assistant.",
    "funny": "You are sarcastic, witty, and funny.",
    "serious": "You are formal and professional.",
    "anime": "You speak like an anime character with dramatic flair.",
    "villain": "You are a dramatic evil villain.",
    "genius": "You are extremely intelligent and detailed."
}
user_personality = defaultdict(lambda: "default")
allowed_channels = defaultdict(lambda: defaultdict(lambda: None))
cooldowns = {}
COOLDOWN_TIME = 5

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

def is_mentioned(message):
    return bot.user in message.mentions

def is_reply_to_bot(message):
    return (
        message.reference
        and message.reference.resolved
        and message.reference.resolved.author == bot.user
    )

async def generate_embed_reply(message, content):
    embed = discord.Embed(description=content, color=discord.Color.blue())
    embed.set_footer(text="AI Bot ✨")
    await message.reply(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not (is_mentioned(message) or is_reply_to_bot(message)):
        return

    user_id = message.author.id
    guild_id = message.guild.id if message.guild else None

    if guild_id is not None:
        restricted_channel = allowed_channels[guild_id][user_id]
        if restricted_channel is not None and message.channel.id != restricted_channel:
            await message.reply("❌ This bot is restricted to another channel")
            return

    now = time.time()
    if user_id in cooldowns and now - cooldowns[user_id] < COOLDOWN_TIME:
        await message.reply("⏳ Slow down!")
        return
    cooldowns[user_id] = now

    content = message.content.replace(f"<@{bot.user.id}>", "").strip()

    # --- Commands ---
    if content.lower() == "setchannel":
        if guild_id is None:
            await message.reply("❌ This command can only be used in a server.")
            return
        allowed_channels[guild_id][user_id] = message.channel.id
        await message.reply("✅ Bot will now only respond in this channel")
        return

    if content.lower() == "clearchannel":
        if guild_id is None:
            await message.reply("❌ This command can only be used in a server.")
            return
        allowed_channels[guild_id][user_id] = None
        await message.reply("✅ Channel restriction removed. Bot will respond in any channel.")
        return

    if content.lower().startswith("setpersonality"):
        try:
            _, p = content.split(" ", 1)
            if p in personalities:
                user_personality[user_id] = p
                await message.reply(f"✅ Personality set to **{p}**")
            else:
                await message.reply(f"Available personalities: {', '.join(personalities.keys())}")
        except:
            await message.reply("Usage: setpersonality funny")
        return

    if content.lower() == "reset":
        user_memory[user_id] = []
        await message.reply("🧠 Memory cleared!")
        return

    # --- Image generation via Replicate ---
    if content.lower().startswith("image"):
        prompt = content.replace("image", "", 1).strip()
        if not prompt:
            await message.reply("Give me a prompt!")
            return

        if not REPLICATE_API_KEY:
            await message.reply("⚠️ Image generation not configured. Set REPLICATE_API_KEY.")
            return

        await message.reply("🎨 Generating your image, please wait...")

        try:
            headers = {"Authorization": f"Token {REPLICATE_API_KEY}"}
            payload = {
                "version": "db21e45a6e4a1ff5e6fa9b5f6b3b9b7c7a20c4c4b8e9f7e3e6f1d2c3a4b5c6d7",  # Stable Diffusion v2
                "input": {"prompt": prompt, "width": 512, "height": 512}
            }
            r = requests.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload)
            r.raise_for_status()
            result = r.json()
            prediction_url = result["urls"]["get"]

            # Poll until done
            while True:
                r2 = requests.get(prediction_url, headers=headers)
                r2.raise_for_status()
                status = r2.json()["status"]
                if status == "succeeded":
                    image_url = r2.json()["output"][0]
                    await message.channel.send(f"🖼️ {image_url} (prompt: **{prompt}**)")
                    break
                elif status == "failed":
                    await message.reply("⚠️ Image generation failed.")
                    break
        except Exception as e:
            print("Image generation error:", e)
            await message.reply("⚠️ Image generation failed. Check your API key or network.")
        return

    # --- Attachments ---
    if message.attachments:
        file = message.attachments[0]
        if file.filename.endswith((".txt", ".py", ".json")):
            text = await file.read()
            content += "\n\nFile content:\n" + text.decode("utf-8")[:2000]

    # --- Add to memory ---
    user_memory[user_id].append({"role": "user", "content": content})
    user_memory[user_id] = user_memory[user_id][-12:]

    # --- Chat via Groq ---
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": personalities[user_personality[user_id]] + " Reply in the user's language."},
                *user_memory[user_id]
            ]
        )
        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        await generate_embed_reply(message, reply)
    except Exception as e:
        print("Chat error:", e)
        await message.reply("⚠️ AI error.")

bot.run(DISCORD_TOKEN)
