# PREFERENCES ---------------------------------------------------------------
maxWPM = 15                   # max CW speed is 15 wpm
TELNET_TIMEOUT = 60  # 300          # time out for telnet [s], 5m
MIN_INTERVAL_TELEGRAM = 30    # minimum interval between Telegram posts [s]
MSG_LIFETIME = 600            # time before deleting the notifications [s], 10m

BOT_INTERVAL = 5              # BOT polling interval [s]
BOT_TIMEOUT = 30              # time out for Telegram BOT [s]

HOST = "telnet.reversebeacon.net"  # RBN telnet server
port = 7000                        # telnet port

DEBUG = True	  # Debug logging level (False is no output).
VERSION = '0.3'
AUTHOR = 'MG (iv3ifz)'

# icons for Telegram, depicting which continent the spot is from
icons = {'EU': '🔵', 'NA': '🔴', 'SA': '⭕',
         'AF': '🟣', 'AN': '🟤', 'AS': '🟢', 'OC': '🟡'}

# Pinned message
pinned = '**⏼ LINK ON**!\nLegend: EU🔵, NA🔴, SA⭕, AS🟢, AF🟣, AN🟤, OC🟡\n\n📣 **Skeds:** announce UR CALL, QRG, WPM\nby sending "/help" to @theslowmorsecodeclub_bot'
# -----------------------------------------------------------------------------
