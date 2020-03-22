from enum import Enum

class Mode(Enum):
  first = '最初の人のみ'
  all = '全員'

  @classmethod
  def value_of(cls, target_value):
    for e in Mode:
      if e.name == target_value:
        return e
    raise ValueError("%sは有効なモードではありません" % target_value)

class Server(object):
  
  def __init__(self, guild_id, notification_channel, mode = Mode.first, mention_everyone = False):
    self.guild_id = guild_id
    self.notification_channel = notification_channel
    self.mode = mode
    self.mention_everyone = mention_everyone
  
  



