import discord
from discord.ext import commands
import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta

client = commands.Bot(command_prefix="!")
token = os.environ['DISCORD_BOT_TOKEN']
database_url = os.environ.get('DATABASE_URL')
data_mem = dict()

def get_connection():
    return psycopg2.connect(database_url)

def get_value_by_server_id(server_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT voice_notification_channel as ch_id FROM server_info WHERE server_id='%s'" % (server_id,))
            result = cur.fetchone()
            if result == None:
                return None
            return dict(result)

def get_all_data():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT server_id as server_id, voice_notification_channel as ch_id FROM server_info")
            result = cur.fetchall()
            return result

def upsert_channel_id(server_id, channel_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("INSERT INTO server_info VALUES ('%s', '%s') ON CONFLICT ON CONSTRAINT server_info_pkey DO UPDATE SET voice_notification_channel='%s'" % (server_id, channel_id, channel_id))
        conn.commit()

def get_channel_id_or_default(guild):
    channel = get_value_by_server_id(guild.id)
    if channel == None:
        upsert_channel_id(guild.id, guild.text_channels[0].id)
        return guild.text_channels[0].id
    return channel["ch_id"].strip()

@client.event
async def on_ready():
    global data_mem
    all_data = get_all_data()
    if all_data != None:
        for key,value in all_data:
            data_mem[key.strip()] = value.strip()

@client.event
async def on_guild_join(guild):
    global data_mem
    data_mem[str(guild.id)] = get_channel_id_or_default(guild)

@client.command()
async def oma(ctx, arg=None):
    global data_mem
    if arg == None:
        return
    if arg == 'update':
        upsert_channel_id(ctx.message.guild.id, ctx.message.channel.id)
        data_mem[str(ctx.message.guild.id)] = ctx.message.channel.id
        await ctx.send("Notification Channel is updated to %s" % ctx.message.channel)
    

@client.event
async def on_voice_state_update(member, before, after):
    global data_mem
    channel_id = data_mem.get(str(member.guild.id))
    if channel_id == None:
        channel_id = get_channel_id_or_default(member.guild)
        data_mem[str(member.guild.id)] = channel_id

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
