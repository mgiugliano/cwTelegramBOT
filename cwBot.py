#
# THIS IS A MODULE AND NOT THE MAIN PROGRAM
#
# cwBOT Module ---> sked and QRS cw spotter bot
# RBN to Telegram BOT Gateway
#
# Michele Giugliano - Feb 2022
#
# REQUIREMENTS:
# pip3 install requests pyTelegramBotAPI call_to_dxcc
#

from prefs import *                 # Import preferences (prefs.py)
from config_private import *        # Import private credentiale (prefs.py)
from timeit import default_timer as timer   # Estimating elapsed time
from time import time as tm                 # Checking current UNIX timestamp
import sys
import time                         # Sleeping for a while and check UNIX time
import os               # Lib for interacting with files on disk
import re               # Lib for regular expressions checking sked info entered
import threading        # Lib to perform multithreading
import requests         # Lib to perform http POST requests
import json             # Lib to handled json data
import call_to_dxcc     # Lib to get country & continent from a (ham) call sign
import telebot          # Lib to prepackaged data for communicating to Telegram
import telnetlib        # Library to perform telnet link to RBN


DEBUG = False	  # Debug logging level (False is no output).

# Required libraries and imported Python functions ----------------------------

# sked = ''        # global variable (skeds)
# excluded = []    # global variable (list of excluded spots)
# club = []        # global variable (highlighted spots and skeds)
# banned = []      # global variable (banned Telegram users)

bot = ''
queue = ''       # global variable (message queue initialised)
sked = ''

# -----------------------------------------------------------------------------
# DO NOT CHANGE THE FOLLOWING LINES
target_url = 'https://api.telegram.org/bot' + API_TOKEN + '/sendMessage'
payload = {'chat_id': chat_id,
           'disable_notification': 'true',
           'disable_web_page_preview': 'true',
           # See https://core.telegram.org/bots/api#markdownv2-style
           'parse_mode': 'MarkdownV2',
           'text': 'message text goes here'}
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Ultra-simple debugging function: it prints out
# messages to the standard output (console) if the
# global variable DEBUG is set to True
def log(s):
    if DEBUG:
        timetag = time.strftime("%Y%b%d-%H%M%S")
        print(timetag + ' ' + s)


# Ultra-simple debugging function: it prints out
# messages to the standard error (console) if the
# global variable DEBUG is set to True
def logerror(s):
    # if DEBUG:
    timetag = time.strftime("%Y%b%d-%H%M%S")
    print(timetag + ' ' + s, file=sys.stderr)


# Text list reading from ASCII file: it loads individual lines from a file
# into the elements of a list of strings.
def readfile(filename):
    output = []                               # Empty list (if error)
    try:
        tmp_file = open(filename, "r")            # Open the ASCII file...
        tmp = tmp_file.read()                     # Read its content...
        output = tmp.split("\n")                  # Split by '\n'...
        tmp_file.close()                          # Close the file...
        output = list(filter(None, output))       # Remove empty lines.
    except Exception as e:
        logerror('Error: reading ' + filename +
                 ' failed! Exception occurred: {}'.format(e))
    return output                                # Return the list of lines


def botONLINE():  # Announce the bot is online
    #
    log("Hello, BOT is ONLINE!")


def botOFFLINE():  # Announce the bot is offline
    #
    log("Hello, BOT is OFFLINE!")


# Internal function, dealing with logging on the telnet server of RBN.
# It tries to connect once, and if it fails, returns "None".
def _logon_telnet_server():  # Connect to RBN server & returns a telnet session
    try:
        log('Connecting to ' + HOST + ' via telnet...')
        tn = telnetlib.Telnet(HOST, port, timeout=TELNET_TIMEOUT)
        log('Connected!')
        time.sleep(0.5)

        line = tn.read_until(b"Please enter your call: ", timeout=10)
        tn.write(USR + b"\n")
        log("Login successful!")
        return tn                              # Return the telnet object

    except Exception as e:
        logerror('Error: _logon failed! Exception occurred: {}'.format(e))
        return None                            # Return None if error
# -----------------------------------------------------------------------------


# External function, dealing with logging on the telnet server of RBN.
# It tries to connect once, and if it fails, it tries again indefinitely.
def logon():  # Connect to RBN server & returns a telnet session
    tn = _logon_telnet_server()
    while tn is None:
        log("Retrying logging on...")
        tn = _logon_telnet_server()
        time.sleep(3)

    return tn


#
# External function, dealing with getting messages from RBN.
#
def getspot(tn):   # Get data from telnet.reversebeacon.net or signal timeout
    try:
        line = tn.read_until(b"\n", TELNET_TIMEOUT)  # Read until newline
    except Exception as e:     # except EOFError as error:
        logerror('Error: getspot() failed! Exception occurred: {}'.format(e))
        return None

    if line == b'':           # If no data received, return None
        logerror("Error: getspot() failed! No data received!")
        return None             # (it also happens when read_until times out)
    else:                       # Otherwise,...
        out = _parse_RNB_message(line)  # parse the message and
        #log("Spot received!")
        return out                      # return the parsed data as a dict
# -----------------------------------------------------------------------------


#
# Internal function, dealing with parsing messages from RBN.
#
def _parse_RNB_message(line):  # Parse RBN spot msg and returns a dictionary
    # We look for the following string formatting (reversebeacon.net):
    # DX de EY8ZE-#:    3563.0  IR1WRTC        CW    11 dB  28 WPM  CQ  2255Z
    # 0   1    2          3        4            5     6  7   8  9   10    11

    out = dict()                # Prepare output data structure (now empty)

    if b'DX' in line:             # If DX line found, parse the information
        line = line.decode("utf-8")  # Convert to string
        line = line.strip()            # Remove newline character
        line = line.split()            # Split into an array for parsing

        if len(line) < 8:              # If the line is NOT well-formed
            logerror('Error: malformed DX line: ' + line)
            return out                  # Return empty data if error

        isCW = line[5] == 'CW'         # Check for the CW/RTTY flag
        speed = int(line[8])           # Extract wpm (as integer)
        isIncluded = not (line[4] in excluded)  # Call NOT among excluded ones

        # Proceed only if it is CW, QRS, and the callsign is not excluded...
        if isCW and (speed < maxWPM) and isIncluded:

            spotter = line[2]                    # Extract spotter call
            spotter = spotter[0:len(spotter)-3]  # Remove trailing '-#:'

            try:    # Get continent of the spotter
                _, continent, _ = call_to_dxcc.data_for_call(spotter)
                try:
                    icon = icons[continent]
                except KeyError:
                    icon = "◯"
            except call_to_dxcc.DxccUnknownException:
                continent = '  '         # Unknown continent
                icon = "◯"               # Unknown continent icon

            isfriend = "💚" if line[4] in club else ""  # Check if friend

            out['continent'] = continent        # Add spotter's continent
            out['icon'] = icon                  # Add spotter's continent icon
            out['call'] = line[4]               # Add call to output data
            out['freq'] = line[3]               # Add frequency to output data
            out['speed'] = str(speed)           # Add speed to output data
            out['isfriend'] = isfriend          # Add 'friend' icon, if any
        else:
            log("Spot rejected: no QRS or in excluded-list.")

    # Return the output data structure (empty if no DX or CW QRS line found)
    return out


#
# External function, dealing with preparing the message for Telegram
#
def prepare_message(out):
    # It is assumed that out != None
    if len(out) != 6:       # If data is invalid, return empty message
        logerror("Error: prepare_message() failed! Data invalid!")
        logerror(out)
        return ''           # timeout or NOT a "spot" line received

    continent = out['continent']
    icon = out['icon']
    call = out['call']
    freq = out['freq']
    speed = out['speed']
    isfriend = out['isfriend']

    speed = '*%swpm*' % speed
    spotterloc = "[de %s]" % continent

    # Prepare the content of the QRZ link
    ecall = call.replace('/', '\\/')    # Escape '/' in callsign
    ecall = ecall.replace('.', '\\.')   # Escape '.' in callsign
    hcall = '[%s%s](https://www.qrz.com/db/%s)' % (isfriend, ecall, call)

    # Prepare message for automated linking a WebSDR to the same frequency
    efreq = freq.replace('.', '\\.')    # Escape '.' in frequency
    if (float(freq) > 29000):   # If freq is above 29 kHz, don't use UTwente
        hfreq = '%s k' % (efreq)
    else:
        hfreq = '[%s k](http://websdr.ewi.utwente.nl:8901/\\?tune\\=%scw)' % (efreq, freq)

    spot = "%s►%s %s\t%s\t%s" % (icon, speed, hcall, spotterloc, hfreq)
    log("Message ready: " + spot)
    return spot
# -----------------------------------------------------------------------------


#
# External function, dealing with filtering Ukrainian OMs, for **their** safety
#
def _is_from_excluded_country(out, newmsg):
    # Check if the callsign must be filtered (as in case of Ukrainian OMs)
    # If so, return True, else return False
    if out['call'][:2] in ['UR', 'US', 'UT', 'UU', 'UV', 'UW', 'UX', 'UY', 'UZ']:
        log("Spot rejected: from excluded country.")
        return True


#
# External function, dealing with checking for duplicate spots
#
def _isduplicate(out, newmsg):
    # Check if the new message is a duplicate of the last message in the queue
    # If so, return True, else return False
    if len(queue) == 0:
        return False  # If queue is empty, it is not (cannot be) a duplicate

    # If the new message entirely appears in the queue, it is a duplicate
    if newmsg in queue:
        log("Duplicate spot found!")
        return True

    n = queue.find(out['call'])  # Check if call appears in the queue
    if n != -1:           # If call appears in the queue, it may be a duplicate
        # if out['icon'] == queue[n-11]:  # If icons are the same => duplicate
        log("Duplicate spot found!")
        return True  # call sign spotted again from same continent => dup

    return False


#
# External function, dealing with queuing the message for Telegram
#
def queue_messages(out, newmsg):  # Add new message to queue
    global queue                    # queue will be modified

    if len(newmsg) > 0:             # Only if new message is not empty
        if out == None:             # If a sked
            queue = queue + '\n' + newmsg  # Add new message to queue
            log("Sked added to the queue.")
        elif not (_isduplicate(out, newmsg) or _is_from_excluded_country(out, newmsg)):
            queue = queue + '\n' + newmsg  # Add new message to queue
            log("Spot added to the queue.")
    # return queue
# -----------------------------------------------------------------------------


#
# External function, dealing with posting a legend and pin it on Telegram
#
def broadcast_to_telegram_legend():  # Broadcast diagnostic message to Telegram
    log("Broadcasting legend to Telegram...")
    payload['text'] = pinned

    try:
        r = requests.post(target_url, data=json.dumps(payload), headers={
            'Content-Type': 'application/json'})
        result = r.ok
    except Exception as e:
        logerror(
            'Error: broadcast_to_telegram_legend() failed! Exception occurred: {}'.format(e))
        result = False

    if result:                # If request was successful (HTTP 200)
        log("Broadcasting successful!")
        tmp = r.json()                      # Extract JSON data
        tmq = tmp['result']                 # Extract 'result' data
        msg_id = str(tmq['message_id'])     # Extract message ID

        mytarget_url = 'https://api.telegram.org/bot' + API_TOKEN + '/pinChatMessage'
        payload = {'chat_id': chat_id,
                   'message_id': msg_id,
                   'disable_notification': True}
        try:
            r = requests.post(mytarget_url, data=json.dumps(
                payload), headers={'Content-Type': 'application/json'})
        except Exception as e:
            logerror("Error: broadcast_to_telegram_legend() pinning failed!")
    else:
        logerror("Error: broadcast_to_telegram_legend() failed!")
# -----------------------------------------------------------------------------


#
# External function, dealing with broadcasting to Telegram
#
def broadcast_to_telegram(msg):     # Broadcast message to Telegram
    if len(msg) > 0:                # Only if message is not empty
        log("Broadcasting to Telegram...")
        payload['text'] = msg

        r = None
        try:
            r = requests.post(target_url, data=json.dumps(payload), headers={
                              'Content-Type': 'application/json'})
        except Exception as e:
            logerror("Error: broadcast_to_telegram()/requests.post failed!")

        if r == None:
            return

        if r.ok:                # If request was successful (HTTP 200)
            log("Broadcasting successful!")
            tmp = r.json()                      # Extract JSON data
            tmq = tmp['result']                 # Extract 'result' data
            msg_id = str(tmq['message_id'])     # Extract message ID
            msg_date = str(tmq['date'])

            sent_msgs = open("sent_msgs.tmp", 'a')   # Open sent_msgs.tmp
            sent_msgs.write(msg_date + ' ' + msg_id +
                            '\n')  # Add msg ID to file
            sent_msgs.close                         # Close sent_msgs.tmp
        else:
            logerror("Error: broadcast_to_telegram() failed!")
# -----------------------------------------------------------------------------


#
# External function, dealing with deleting a message from Telegram
#
def delete_posted_message(msg_id):
    mytarget_url = 'https://api.telegram.org/bot' + API_TOKEN + '/deleteMessage'
    payload = {'chat_id': chat_id,
               'message_id': msg_id}
    try:
        r = requests.post(mytarget_url, data=json.dumps(
            payload), headers={'Content-Type': 'application/json'})
        return r.ok
    except Exception as e:
        logerror("Error: delete_posted_message() pinning failed!")
        return False
# -----------------------------------------------------------------------------


#
# External function, dealing with deleting all old messages from Telegram
#
def delete_old_messages():
    #print("\nExamining old messages for possible deletions...")
    if os.stat("sent_msgs.tmp").st_size > 0:
        sent_msgs = open("sent_msgs.tmp", 'r')   # Open sent_msgs.tmp
        lines = sent_msgs.readlines()           # Read all lines from sent_msgs.tmp
        sent_msgs.close                         # Close sent_msgs.tmp

        # Now the entire file is read into memory, so we can delete old messages

        now = int(tm())                 # Get current time in UNIX timestamp
        toBeDeleted = []                # Create empty list for message IDs to be deleted

        for idx, line in enumerate(lines):  # For each line in sent_msgs.tmp
            line = line.strip()         # Remove newline character
            lineArr = line.split()      # Split line into array
            msg_date = int(lineArr[0])  # Extract date
            msg_id = lineArr[1]         # Extract message ID

            if (now - msg_date) > MSG_LIFETIME:
                log('Message ' + msg_id + ' is too old: attempting deletion...')
                result = delete_posted_message(msg_id)
                if result:
                    # Add index to list of IDs to be deleted
                    toBeDeleted.append(idx)
                    log("Succeeded! Adding to the pruning list...")
                else:
                    log("Failed! Is Telegram or internet down?!?")

        if toBeDeleted:                 # If there are IDs to be deleted
            log('Pruning ' + str(len(toBeDeleted)) + ' deleted messages...')

            sent_msgs = open("sent_msgs.tmp", 'w')   # Open sent_msgs.tmp
            for id, line in enumerate(lines):  # For each line in sent_msgs.tmp
                # Write all (remaining) lines to file
                if id not in toBeDeleted:
                    sent_msgs.write(line)
            sent_msgs.close                  # Close sent_msgs.tmp
# -----------------------------------------------------------------------------


def bot_polling():
    global bot  # Keep the bot object as global variable if needed
    log("Starting Telegram bot polling now...")
    while True:
        log("New Telegram bot instance started!")
        bot = telebot.TeleBot(API_TOKEN)  # Generate new bot instance
        # If bot is used as a global variable, remove bot as an input param
        botactions(bot)
        try:
            bot.polling(none_stop=True, interval=BOT_INTERVAL,
                        timeout=BOT_TIMEOUT)
        except Exception as ex:  # Error in polling
            logerror("Telegram Bot polling failed, restarting in {}sec. Error:\n{}".format(
                BOT_TIMEOUT, ex))
            bot.stop_polling()
            time.sleep(BOT_TIMEOUT)
        else:  # Clean exit
            bot.stop_polling()
            log("Telegram bot polling loop finished.")
            break  # End loop
# -----------------------------------------------------------------------------


def botactions(bot):
    global sked
    # Set all your bot handlers inside this function

    @ bot.message_handler(commands=["start"])
    def command_start(message):
        bot.reply_to(
            message, "USE:  /sked MYCALL FREQ(in kHz) SPEED(in wpm)\nE.G.: /sked iv3xxx 14050.3 15")

    @ bot.message_handler(commands=["sked"])
    def command_start(message):
        user_first_name = str(message.from_user.first_name)
        user_id = str(message.from_user.id) + '\n'
        # message.from_user.id
        # message.from_user.first_name
        # message.from_user.last_name
        # message.from_user.username

        if os.stat("sent_msgs.tmp").st_size > 0:
            fbanned = open("ban_list.tmp", 'r')   # Open ban_list.tmp
            banned = fbanned.readlines()          # Read all lines from ban_list.tmp
            fbanned.close                         # Close ban_list.tmp

        if user_id in banned:
            log("User {} is banned!".format(user_id))
            bot.reply_to(
                message, "⛔ Ban in place! Contact the admin if this is a mistake.")
            return

        tmp = message.text.split()[1:]
        if (len(tmp) != 3):
            bot.reply_to(message, "⛔ Syntax error!\nType /start")
            return
        else:
            call = tmp[0]
            freq = tmp[1]
            speed = tmp[2]

        # bot.reply_to(message, "You entered: " + call + ' ' + freq + ' ' + speed)

        call = call.upper()

        if len(call) > 10:
            bot.reply_to(
                message, "⛔ Entered call is too long! Is it authentic?\nType /start")
            return

        if not bool(re.match('^[1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ//]+$', call)):
            bot.reply_to(
                message, "⛔ Entered call contains illegal characters!\nType /start")
            return

        try:
            tmq = float(freq)
        except ValueError:
            bot.reply_to(
                message, "⛔ Entered frequency must be numeric only (in kHz)!\nType /start")
            return

        if not speed.isnumeric():
            bot.reply_to(
                message, "⛔ Entered speed must be numeric only (in wpm)!\nType /start")
            return

        speed = int(speed)

        if (speed <= 0 or speed >= 50):
            bot.reply_to(
                message, "⛔ Entered speed is out of range [0 - 50] wpm!\nType /start")
            return

        # ----------------------------------------------------------------------

        freq = str(tmq)

        isfriend = "💚" if call in club else ""  # Check if friend

        ecall = call.replace('/', '\\/')
        ecall = ecall.replace('.', '\\.')
        hcall = '[%s%s](https://www.qrz.com/db/%s)' % (isfriend, ecall, call)

        # freq  = '7000.0'
        if (float(freq) > 29000):
            efreq = freq.replace('.', '\\.')
            hfreq = '%s k' % (efreq)
        else:
            efreq = freq.replace('.', '\\.')
            hfreq = '[%s k](http://websdr.ewi.utwente.nl:8901/\\?tune\\=%scw)' % (efreq, freq)

        # speed = 15
        speed = '*%dwpm*' % (speed)

        # print('A user added a sked!')
        # sked = "●%s: %s\t       %s" % (speed, hcall, hfreq)
        sked = "📣►%s: %s\t      \t%s" % (speed, hcall, hfreq)

        bot.reply_to(message, "🟢Ok, " + user_first_name + "!\nI am now queuing your sked.\nIt will be broadcasted on Telegram and will be deleted after " +
                     str(round(MSG_LIFETIME/60.)) + " minutes.")

        sent_msgs = open("sked_log.txt", 'a')   # Open sked_log.tmp
        sent_msgs.write(str(tm()) + ' ' + call + ' ' +
                        freq + ' ' + speed + ' ' + user_id + '\n')
        sent_msgs.close                         # Close sent_msgs.tmp


def refresh_config_informations():
    global excluded
    global club
    global banned

    # =============================================================================
    # Let's now import a series of "private" config file (NOT in the public repo)
    # containing excluded callsigns (not to spot): 50 MHz beacons, etc.
    # I  used https://www.keele.ac.uk/depts/por/50.htm
    #
    log("Reading excluded callsigns...")
    excluded = readfile("./config/excluded.txt")  # Read excluded callsigns
    log(str(len(excluded)) + " call signs acquired.")

    # ...containing callsigns (QRS lovers, e.g. The Slow Morse Club members)
    log("Reading QRS/friends/club callsigns...")
    club = readfile("./config/club.txt")  # Read "club" callsigns
    log(str(len(club)) + " call signs acquired.")

    # ...or containing banned telegram users (telegram user IDs, not call signs)
    log("Reading banned Telegram users...")
    banned = readfile("./config/ban_list.txt")  # Read banned telegram users
    log(str(len(banned)) + " banned users acquired.")
# -----------------------------------------------------------------------------

# =============================================================================
