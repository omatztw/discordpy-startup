import discord
from discord.ext import commands
import os
import psycopg2
import requests
from psycopg2.extras import DictCursor
from datetime import datetime, timedelta
from server_info import Server, Mode, ServerType


client = commands.Bot(command_prefix="!")
token = os.environ['DISCORD_BOT_TOKEN']
database_url = os.environ.get('DATABASE_URL')
sheet_url = os.environ.get('SHEET_URL')
sheet_url_dict = {
    'elph': os.environ.get('SHEET_URL_ELPH'),
    'rose': os.environ.get('SHEET_URL_ROSE'),
    'moen': os.environ.get('SHEET_URL_MOEN')
}
data_mem = dict()

def get_connection():
    return psycopg2.connect(database_url)

def get_value_by_server_id(server_id):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT voice_notification_channel as ch_id, mode as mode, mention_everyone as mention_everyone, notify as notify, server_type as server_type FROM server_info WHERE server_id='%s'" % (server_id,))
            result = cur.fetchone()
            if result == None:
                return None
            return dict(result)

def get_all_data():
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT server_id as server_id, voice_notification_channel as ch_id, mode as mode, mention_everyone as mention_everyone, notify as notify, server_type as server_type FROM server_info")
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
            cur.execute("UPDATE server_info SET mode = '%s' WHERE server_id = '%s'" % (mode.name, server_id))
        conn.commit()

def change_server(server_id, server_type):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE server_info SET server_type = '%s' WHERE server_id = '%s'" % (server_type.name, server_id))
        conn.commit()

def update_mention_everyone(server_id, mention_everyone):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE server_info SET mention_everyone = '%s' WHERE server_id = '%s'" % (mention_everyone, server_id))
        conn.commit()

def update_notify(server_id, notify):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("UPDATE server_info SET notify = '%s' WHERE server_id = '%s'" % (notify, server_id))
        conn.commit()

def get_channel_info_or_default(guild):
    channel = get_value_by_server_id(guild.id)
    if channel == None:
        channel_id = guild.text_channels[0].id
        if guild.system_channel:
            channel_id = guild.system_channel.id
        upsert_channel_id(guild.id, channel_id)
        return Server(guild.id, channel_id)
    return Server(guild.id, channel["ch_id"], Mode.value_of(channel["mode"]), channel["mention_everyone"], channel["notify"], ServerType.value_of(channel["server_type"]))

def str2bool(s):
     return s.lower() in ["true", "t", "yes", "1", "on"]

def get_raid_time(server_type = 'elph'):
    headers = {"content-type": "application/json"}
    response = requests.get(sheet_url_dict[server_type], headers=headers).json()
    ron_list =  [datetime.strptime(x, '%Y/%m/%d %H:%M:%S').strftime('%H:%M:%S') for x in response["ron"]]
    modafu_list =  [datetime.strptime(x, '%Y/%m/%d %H:%M:%S').strftime('%H:%M:%S') for x in response["modafu"]]
    msg = """```
 ゴルロン    ゴルモダフ
+----------+----------+
| %s | %s |
+----------+----------+
| %s | %s |
+----------+----------+
| %s | %s |
+----------+----------+
```""" % (
        ron_list[0], modafu_list[0],
        ron_list[1], modafu_list[1],
        ron_list[2], modafu_list[2]
        )
    return msg

@client.event
async def on_ready():
    global data_mem
    all_data = get_all_data()
    if all_data != None:
        for key,ch_id, mode, mention_everyone, notify, server_type in all_data:
            data_mem[key] = Server(key, ch_id, Mode.value_of(mode), mention_everyone, notify, ServerType.value_of(server_type))

@client.event
async def on_guild_join(guild):
    global data_mem
    data_mem[str(guild.id)] = get_channel_info_or_default(guild)

@client.command()
async def oma(ctx, *arg):
    global data_mem
    if len(arg) == 0:
        return
    if arg[0] == 'update':
        upsert_channel_id(ctx.message.guild.id, ctx.message.channel.id)
        data_mem[str(ctx.message.guild.id)].notification_channel = ctx.message.channel.id
        await ctx.send("通知するチャンネルを[%s]に変更しました。" % ctx.message.channel)
    
    if arg[0] == 'set_server' or arg[0] == 'ss':
        if len(arg) != 2 or (arg[1] not in [e.name for e in ServerType]):
            await ctx.send("Usage: `!oma set_server %s`" %  [e.name for e in ServerType])
            return
        server_type = ServerType.value_of(arg[1])
        change_server(ctx.message.guild.id, server_type)
        data_mem[str(ctx.message.guild.id)].server_type = server_type
        await ctx.send("サーバーを[%s]に変更しました。" % server_type.value)

    
    if arg[0] == 'raid':
        msg = get_raid_time(data_mem[str(ctx.message.guild.id)].server_type.name)
        await ctx.send(msg)
    
    if arg[0] == 'mode':
        if len(arg) != 2 or (arg[1] not in [e.name for e in Mode]):
            await ctx.send("Usage: `!oma mode %s`" %  [e.name for e in Mode])
            return
        mode = Mode.value_of(arg[1])
        change_mode(ctx.message.guild.id, mode)
        data_mem[str(ctx.message.guild.id)].mode = mode
        await ctx.send("通知モードを[%s]に変更しました。" % mode.value)

    if arg[0] == 'mention':
        if len(arg) != 2 or (arg[1] not in ['yes', 'no']):
            await ctx.send("Usage: `!oma mention %s`" %  ['yes', 'no'])
            return
        
        update_mention_everyone(ctx.message.guild.id, str2bool(arg[1]))
        data_mem[str(ctx.message.guild.id)].mention_everyone = str2bool(arg[1])
        await ctx.send("全員へのメンションを[%s]に変更しました。" % arg[1])

    if arg[0] == 'notify':
        if len(arg) != 2 or (arg[1] not in ['on', 'off']):
            await ctx.send("Usage: `!oma notify %s`" %  ['on', 'off'])
            return
        
        update_notify(ctx.message.guild.id, str2bool(arg[1]))
        data_mem[str(ctx.message.guild.id)].notify = str2bool(arg[1])
        await ctx.send("通知機能を[%s]に変更しました。" % arg[1])

@client.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
        
    global data_mem
    guild_id = str(member.guild.id)
    channel = data_mem.get(guild_id)
    if channel == None:
        channel = data_mem[guild_id] = get_channel_info_or_default(member.guild)
    
    if not channel.notify:
        return
    
    alert_channel = client.get_channel(int(channel.notification_channel))

    if alert_channel is None:
        print("alert channel is not found.. already deleted? GUILD: %s NOTIFICATION_CH: %s" % (channel.guild_id, channel.notification_channel) )
        return

    msg = ''
    if channel.mention_everyone:
        msg += '@everyone '

    if before.channel != after.channel:
        now = datetime.utcnow() + timedelta(hours=9)
        if before.channel is None:
            mode = channel.mode
            if mode == Mode.all or len(list(filter(lambda m: not m.bot, after.channel.members))) == 1:
                msg += f'[{member.name}]さんがチャンネル[{after.channel.name}]で通話を始めました。'
                await alert_channel.send(msg)
        # elif after.channel is None: 
        #     if len(list(filter(lambda m: not m.bot, before.channel.members))) == 0:
        #         msg = f'{now:%m/%d-%H:%M} にチャンネル[{before.channel.name}]の通話が終了しました。'
        #         await alert_channel.send(msg)

    if not before.self_stream and after.self_stream:
        now = datetime.utcnow() + timedelta(hours=9)
        msg += f'[{member.name}]さんがチャンネル[{after.channel.name}]でライブ配信を始めました。'
        await alert_channel.send(msg)

client.run(token)
