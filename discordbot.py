import discord
import os
from datetime import datetime, timedelta

client = discord.Client()
token = os.environ['DISCORD_BOT_TOKEN']
channel_id = os.environ['CHANNEL_ID']

@client.event
async def on_voice_state_update(member, before, after): 
    if member.bot:
        return
    if before.channel != after.channel:
        now = datetime.utcnow() + timedelta(hours=9)
        alert_channel = client.get_channel(int(channel_id))
        if before.channel is None: 
            msg = f'{now:%m/%d-%H:%M} に {member.name} が {after.channel.name} に参加しました。'
            await alert_channel.send(msg)
        elif after.channel is None: 
            msg = f'{now:%m/%d-%H:%M} に {member.name} が {before.channel.name} から退出しました。'
            await alert_channel.send(msg)

client.run(token)
