import discord
import os
import io
import time
import base64
from collections import defaultdict
from groq import Groq

# Environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# 🧠 Memory per user
user_memory = defaultdict(list)

# 🎭 Personalities
personalities = {
    "default": "You are a helpful and friendly assistant.",
    "funny": "You are sarcastic, witty, and funny.",
    "serious": "You are formal and professional.",
    "anime": "You speak like an anime character with dramatic flair.",
    "villain": "You are a dramatic evil villain.",
    "genius": "You are extremely intelligent and detailed."
}
user_personality = defaultdict(lambda: "default")

# 📌 Channel restrictions (guild_id -> user_id -> channel_id)
allowed_channels = defaultdict(lambda: defaultdict(lambda: None))

# 🛡️ Cooldown
cooldowns = {}
COOLDOWN_TIME = 5  # seconds

# ✅ Bot ready
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# Check if bot is mentioned
def is_mentioned(message):
    return bot.user in message.mentions

# Check if message is a reply to bot
def is_reply_to_bot(message):
    return (
        message.reference
        and message.reference.resolved
        and message.reference.resolved.author == bot.user
    )

# Embed reply
async def generate_embed_reply(message, content):
    embed = discord.Embed(description=content, color=discord.Color.blue())
    embed.set_footer(text="AI Bot ✨")
    await message.reply(embed=embed)

# Main message handler
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not (is_mentioned(message) or is_reply_to_bot(message)):
        return

    user_id = message.author.id
    guild_id = message.guild.id if message.guild else None

    # 📌 Channel restriction check
    if guild_id is not None:
        restricted_channel = allowed_channels[guild_id][user_id]
        if restricted_channel is not None and message.channel.id != restricted_channel:
            await message.reply("❌ This bot is restricted to another channel")
            return

    # 🛡️ Cooldown check
    now = time.time()
    if user_id in cooldowns and now - cooldowns[user_id] < COOLDOWN_TIME:
        await message.reply("⏳ Slow down!")
        return
    cooldowns[user_id] = now

    # Remove bot mention from content
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()

    # 📌 Commands
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

    # 🖼️ Image generation
    if content.lower().startswith("image"):
        prompt = content.replace("image", "", 1).strip()

        if not prompt:
            await message.reply("Give me a prompt!")
            return

        if not GROQ_API_KEY:
            await message.reply("⚠️ Image generation is not configured. Set `GROQ_API_KEY`.")
            return

        await message.reply("🎨 Generating your image, please wait...")

        try:
            # Generate image using Groq
            result = client.images.generate(
                model="stabilityai/stable-diffusion-2",
                prompt=prompt,
                width=512,
                height=512,
            )

            # Extract base64 image from result
            image_base64 = result.images[0]
            image_bytes = io.BytesIO(base64.b64decode(image_base64))

            await message.channel.send(
                f"🖼️ Here's your image for: **{prompt}**",
                file=discord.File(fp=image_bytes, filename="generated.png")
            )

        except Exception as e:
            print("Image generation error:", e)
            await message.reply("⚠️ Image generation failed. Make sure your API key is valid and the model is accessible.")
        return

    # 📁 Read attachments (text files only)
    if message.attachments:
        file = message.attachments[0]
        if file.filename.endswith((".txt", ".py", ".json")):
            text = await file.read()
            content += "\n\nFile content:\n" + text.decode("utf-8")[:2000]

    # 🧠 Memory add
    user_memory[user_id].append({"role": "user", "content": content})
    user_memory[user_id] = user_memory[user_id][-12:]

    # Generate AI reply
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": personalities[user_personality[user_id]] + " Detect and reply in the user's language."
                },
                *user_memory[user_id]
            ]
        )

        reply = response.choices[0].message.content
        user_memory[user_id].append({"role": "assistant", "content": reply})
        await generate_embed_reply(message, reply)

    except Exception as e:
        print("Chat error:", e)
        await message.reply("⚠️ AI error.")

# Run bot
bot.run(DISCORD_TOKEN)
