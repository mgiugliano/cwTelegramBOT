#!/usr/local/bin/python3
#
#!/usr/bin/env python3
#
# MAIN PROGRAM TO LAUNCH
#
# Sked and QRS cw spotter bot
# RBN to Telegram BOT Gateway
#
# Michele Giugliano - March 2022
#

import cwBot as c
# from cwBot import *    # Import the cwBot class


polling_thread = c.threading.Thread(target=c.bot_polling)
polling_thread.daemon = True
polling_thread.start()

# Main program
if __name__ == '__main__':

    c.refresh_config_informations()

    c.log('CW QRS spot/sked bot - starting up...')
    c.log('Feb 2022 - iv3ifz@qsl.net')
    c.log('')

    # Create sent_msgs.tmp if doesn't exist
    tmp = open("sent_msgs.tmp", 'a')
    tmp.close

    # Initialise the Telegram BOT
    c.bot = c.telebot.TeleBot(c.API_TOKEN)

    # Connect to the RBN telnet server
    tn = c.logon()    # Blocking: it waits for the connection to be established
    c.log("Connected: waiting for (QRS) spots...")

    start = c.timer()                     # Initialisation of the timer

    while True:
        # Get (QRS) spots - non blocking (TELNET_TIMEOUT s)
        out = c.getspot(tn)

        while out is None:
            c.logerror("No spot received for " + str(c.TELNET_TIMEOUT) +
                       "sec - trying to reconnect...")
            tn = c.logon()  # Connect to the RBN server
            out = c.getspot(tn)  # Get (QRS) spots

        if len(out) > 0:  # If there is a spot, out is not empty
            spot = c.prepare_message(out)  # Add it to the queue
            #queue = queue_messages(out, spot, queue)
            c.queue_messages(out, spot)

        polling_thread.join(0.0)

        if len(c.sked) > 0:
            log("Adding sked: " + c.sked)
            # broadcast_to_telegram(sked)
            #queue = queue_messages(None, sked, queue)
            queue_messages(None, c.sked)
            c.sked = ''

        end = c.timer()                   # Get the current time
        # How much time [sec] since the last check?
        elapsed = end - start

        if (elapsed > c.MIN_INTERVAL_TELEGRAM):
            c.broadcast_to_telegram(c.queue)
            c.queue = ''
            start = c.timer()

        c.delete_old_messages()
        # print(c.queue)
        c.time.sleep(1)


# Functions avaialble:
#
# def log(s)             ----> diagnotics
# def logerror(s)        ----> diagnotics
# def readfile(filename) ----> read a file into a python list of strings

# def botONLINE()
# def botOFFLINE()

# def logon()                --> connect to the RBN server (and retry if fails)
# def _logon_telnet_server() --> private function, used by logon()

# def getspot(tn)            --> get (QRS) spots
# def _parse_RNB_message(line) --> private function, used by getspot()

# def prepare_message(out)    ---> prepare the spot message for Telegram

# def queue_messages(out, newmsg, queue) ---> add new spot/sked to the queue
# def _isduplicate(out, newmsg, queue)  --> pvt function, by queue_messages()

# def broadcast_to_telegram_legend()
# def broadcast_to_telegram(msg)
# def delete_posted_message(msg_id)
# def delete_old_messages()
# def bot_polling()
# def botactions(bot)
