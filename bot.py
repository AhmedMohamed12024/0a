import discord
import os
from groq import Groq
from collections import defaultdict
import time

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


client = Groq(api_key=GROQ_API_KEY)


intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)

# 🧠 Memory
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

# 🛡️ Cooldown
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
    embed = discord.Embed(
        description=content,
        color=discord.Color.blue()
    )
    embed.set_footer(text="AI Bot ✨")
    await message.reply(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not (is_mentioned(message) or is_reply_to_bot(message)):
        return

    user_id = message.author.id

    # 🛡️ Cooldown
    now = time.time()
    if user_id in cooldowns and now - cooldowns[user_id] < COOLDOWN_TIME:
        await message.reply("⏳ Slow down!")
        return
    cooldowns[user_id] = now

    content = message.content.replace(f"<@{bot.user.id}>", "").strip()

    # 🎭 Set personality
    if content.startswith("setpersonality"):
        try:
            _, p = content.split(" ", 1)
            if p in personalities:
                user_personality[user_id] = p
                await message.reply(f"✅ Personality set to **{p}**")
            else:
                await message.reply(f"Available: {', '.join(personalities.keys())}")
        except:
            await message.reply("Usage: setpersonality funny")
        return

    # 🧠 Reset memory
    if content == "reset":
        user_memory[user_id] = []
        await message.reply("🧠 Memory cleared!")
        return

    # 🖼️ Image generation
    if content.startswith("image"):
        prompt = content.replace("image", "").strip()

        if not prompt:
            await message.reply("Give me a prompt!")
            return

        await message.reply("🚫 Image generation is not available with Groq.")
        return


    # 📁 Read attachments (text only)
    if message.attachments:
        file = message.attachments[0]
        if file.filename.endswith((".txt", ".py", ".json")):
            text = await file.read()
            content += "\n\nFile content:\n" + text.decode("utf-8")[:2000]

    # 🧠 Memory add
    user_memory[user_id].append({"role": "user", "content": content})
    user_memory[user_id] = user_memory[user_id][-12:]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": personalities[user_personality[user_id]] +
                               " Detect and reply in the user's language."
                },
                *user_memory[user_id]
            ]
        )

        reply = response.choices[0].message.content

        user_memory[user_id].append({"role": "assistant", "content": reply})

        await generate_embed_reply(message, reply)

    except Exception as e:
        print(e)
        await message.reply("⚠️ AI error.")

bot.run(DISCORD_TOKEN)