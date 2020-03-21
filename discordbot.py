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
MODE_STR = {
    'first': '最初の人のみ',
    'all': '全員'
}

def get_connection():
    return psycopg2.connect(database_url)

def get_value_by_server_id(server_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT voice_notification_channel as ch_id, mode as mode FROM server_info WHERE server_id='%s'" % (server_id,))
            result = cur.fetchone()
            if result == None:
                return None
            return dict(result)

def get_all_data():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT server_id as server_id, voice_notification_channel as ch_id, mode as mode FROM server_info")
            result = cur.fetchall()
            return result

def upsert_channel_id(server_id, channel_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("INSERT INTO server_info VALUES ('%s', '%s') ON CONFLICT ON CONSTRAINT server_info_pkey DO UPDATE SET voice_notification_channel='%s'" % (server_id, channel_id, channel_id))
        conn.commit()

def change_mode(server_id, mode):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE server_info SET mode = '%s' WHERE server_id = '%s'" % (mode, server_id))
        conn.commit()

def get_channel_info_or_default(guild):
    channel = get_value_by_server_id(guild.id)
    if channel == None:
        upsert_channel_id(guild.id, guild.text_channels[0].id)
        return guild.text_channels[0].id, 'first'
    return channel["ch_id"].strip(), channel["mode"]

def get_mode(guild):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT mode as mode FROM server_info WHERE server_id = '%s'" % guild.id)
            result = cur.fetchone()
            if result == None:
                return None
            return dict(result)

@client.event
async def on_ready():
    global data_mem
    all_data = get_all_data()
    if all_data != None:
        for key,ch_id, mode in all_data:
            data_mem[key.strip()] = {'ch_id': ch_id.strip(), 'mode': mode}

@client.event
async def on_guild_join(guild):
    global data_mem
    ch_id, mode = get_channel_info_or_default(guild)
    data_mem[str(guild.id)] = {'ch_id': ch_id, 'mode': mode}

@client.command()
async def oma(ctx, *arg):
    global data_mem
    if len(arg) == 0:
        return
    if arg[0] == 'update':
        upsert_channel_id(ctx.message.guild.id, ctx.message.channel.id)
        data_mem[str(ctx.message.guild.id)]['ch_id'] = ctx.message.channel.id
        await ctx.send("通知するチャンネルを[%s]に変更しました。" % ctx.message.channel)
    
    if arg[0] == 'mode':
        if arg[1] == None or (arg[1] not in ['all', 'first']):
            await ctx.send("Usage: `!oma mode [all, first]`" % ctx.message.channel)
            return
        change_mode(ctx.message.guild.id, arg[1])
        await ctx.send("通知モードを[%s]に変更しました。" % MODE_STR[arg[1]])
    

@client.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
        
    global data_mem
    channel = data_mem.get(str(member.guild.id))
    if channel == None:
        channel_id, mode = get_channel_info_or_default(member.guild)
        data_mem[str(member.guild.id)] = {'ch_id': channel_id, 'mode': mode}
    
    channel = data_mem.get(str(member.guild.id))
    alert_channel = client.get_channel(int(channel['ch_id']))

    if before.channel != after.channel:
        now = datetime.utcnow() + timedelta(hours=9)
        if before.channel is None:
            mode = get_mode(member.guild);
            if mode == 'first' and len(list(filter(lambda m: not m.bot, after.channel.members))) == 1:
                msg = f'{now:%m/%d-%H:%M} に[{member.name}]さんがチャンネル[{after.channel.name}]で通話を始めました。'
                await alert_channel.send(msg)
        # elif after.channel is None: 
        #     if len(list(filter(lambda m: not m.bot, before.channel.members))) == 0:
        #         msg = f'{now:%m/%d-%H:%M} にチャンネル[{before.channel.name}]の通話が終了しました。'
        #         await alert_channel.send(msg)

    if not before.self_stream and after.self_stream:
        now = datetime.utcnow() + timedelta(hours=9)
        msg = f'{now:%m/%d-%H:%M} に[{member.name}]さんがチャンネル[{after.channel.name}]でライブ配信を始めました。'
        await alert_channel.send(msg)

client.run(token)
