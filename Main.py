#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Simple Bot to reply to Telegram messages.
This program is dedicated to the public domain under the CC0 license.
This Bot uses the Updater class to handle the bot.
First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""
from telegram.ext.dispatcher import run_async
import threading
import time
import telegram
import logging
import os
import json
import pickle
import urllib.request
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from oauth2client import client
from oauth2client import tools
import random
import redis
import string

################################################
## Variables required to run program properly ##
################################################

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)

logger = logging.getLogger(__name__)
INPUT_NAME = range(0)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
STUDENT_MAP = "STUDENT_MAP"

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
redis_pickle_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=False)

####################################
#### Google Sheets Commands ########
####################################

#(TODO): Need to store api token in db, not pickle file
def get_service(bot, update, username, token=None):
    """Shows basic usage of the Sheets API.
        Prints values from a sample spreadsheet.
        """
    creds = None
    
    if redis_client.hexists(username, "credentials"):
        creds = pickle.loads(redis_pickle_client.hget(username, "credentials"))

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES)

            # Setup authorization URL
            flow.redirect_uri = InstalledAppFlow._OOB_REDIRECT_URI
            auth_url, _ = flow.authorization_url()

            if not token:
                instructions = """Please follow the instructions to setup a Google Sheet:
                    1. Click on the authorization URL
                    2. Copy the authentication code
                    3. Use '/setup_sheet <authentication_code>' to finish!"""
                keyboard = [[telegram.InlineKeyboardButton("Open URL", url=auth_url)]]
                reply_markup = telegram.InlineKeyboardMarkup(keyboard)
                update.message.reply_text(instructions, reply_markup=reply_markup)

            # Fetch access token if args present
            flow.fetch_token(code=token)
            creds = flow.credentials

            # Save the credentials for the next run
            redis_pickle_client.hset(username, "credentials", pickle.dumps(creds))

    service = build("sheets", "v4", credentials=creds)
    return service


def create_sheet(bot, update, username, token=None):
    """Shows basic usage of the Sheets API.
    Create a new sample spreadsheet.
    """
    service = get_service(bot, update, username, token)

    #(TODO): Sheet might already exist
    # Call the Sheets API
    spreadsheet = {
        "properties": {
            "title": "NUSClassSample.xlsx"
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                        fields="spreadsheetId").execute()
    spreadsheet_id = spreadsheet.get("spreadsheetId")
    redis_client.hset(username, "spreadsheet_id", spreadsheet_id)

##############################
##### Bot framework ##########
##############################

##### Tutor ##########    

def setup_sheet(bot, update, args):
    username = update.message.from_user.username
    # if not redis_client.exists(username):
    #     update.message.reply_text("Invalid command")
    #     return 
    # (TODO): Check if sheet already set up?
    try:
        create_sheet(bot, update, username, args[0])
    except:
        create_sheet(bot, update, username)
    update.message.reply_text("Sheet successfully created!")

def generate_hash(): 
    return hash(time.time()) % 100000000

def start_session(bot, update, args):
    if len(args) != 1:
        update.message.reply_text("Invalid number of arguments")
        return
    number_of_students = int(args[0])
    username = update.message.from_user.username
    if not redis_client.exists(username):
        update.message.reply_text("Invalid command")
        return
    elif redis_client.hexists(username, "session_started"):
        message = "A session is already running"
    else:
        token = generate_hash()
        redis_client.hmset(username, {
            "session_started": 1,
            "num_students": number_of_students,
            "session_token": token,
            "present_students": json.dumps({})
        })
        message = f"Session Started! Token = {token}"
    update.message.reply_text(message)


def stop_session(bot, update):
    username = update.message.from_user.username
    if not redis_client.exists(username):
        update.message.reply_text("Invalid command")
        return
    elif not redis_client.hexists(username, "session_started"):
        message = "No session running"
    else:
        present_students = json.loads(redis_client.hget(username, "present_students"))
        if len(present_students) < int(redis_client.hget(username, "num_students")):
            add_values_to_sheet(bot, update, present_students.copy(), redis_client.hget(username, "spreadsheet_id"), username)
        redis_client.hdel(username, "session_started", "session_token", 
                            "num_students", "present_students")
        message = "Session Stopped"
    update.message.reply_text(message)

##### Student ##########
def start_info(bot, update):
    message = """Hey there! Here's what this bot can do:
        /start: Displays this message
        /setup <name>: Provide IVLE name to the bot
        /attend <token>: Use token provided by tutor to
        indicate attendance"""
    update.message.reply_text(message)
     

def indicate_attendance(bot, update, args):
    username = update.message.from_user.username
    if not redis_client.hexists(STUDENT_MAP, username):
        update.message.reply_text("You must run /setup before indicating attendance")
        return
    elif len(args) != 1:
        update.message.reply_text("Invalid number of arguments")
        return
    token = int(args[0])
    #(TODO): A student may belong to multiple tutors
    for tutor_name in redis_client.scan_iter():
        if tutor_name == STUDENT_MAP or not redis_client.hexists(tutor_name, "session_token"):
            continue
        if int(redis_client.hget(tutor_name, "session_token")) == token:
            update_state(bot, update, username, tutor_name)
            return
    update.message.reply_text("An error occured, please validate token")

# (TODO) Retrieve from DB
def get_ivle_name(username):
    return redis_client.hget(STUDENT_MAP, username)

def update_state(bot, update, username, tutor_name):
    num_students = int(redis_client.hget(tutor_name, "num_students"))
    present_students = json.loads(redis_client.hget(tutor_name, "present_students"))
    name = get_ivle_name(username)
    if username in present_students:
        message = "Attendance already marked!"
    elif num_students == len(present_students):
        message = "Attendance quota filled! Please contact tutor"
    else:
        present_students[username] = name
        redis_client.hset(tutor_name, "present_students", json.dumps(present_students))
        message = "Attendance marked!"
        if num_students == len(present_students):
            add_values_to_sheet(bot, update, present_students.copy(), redis_client.hget(tutor_name, "spreadsheet_id"), tutor_name)
    update.message.reply_text(message)

@run_async
def add_values_to_sheet(bot, update, usernames, spreadsheet_id, tutor_name):
    values = [[name.upper(), "1"] for name in usernames.values()]
    body = {
        "values": values
    }
    # Call the Sheets API
    service = get_service(bot, update, tutor_name)
    # (TODO): Might fail
    result = service.spreadsheets().values().append(
    spreadsheetId=spreadsheet_id, range="A2:B", 
    valueInputOption="RAW", body=body).execute()

def setup_student(bot, update, args):
    try:
        username = update.message.from_user.username
        ivle_name = ' '.join(args)
        print(ivle_name)
        redis_client.hset(STUDENT_MAP, username, ivle_name)
        update.message.reply_text("You have been registered! Please wait " + 
                                    "for your tutor to give you a token")
    except:
        update.message.reply_text("Please enter you IVLE name with the command" +  
                                    " in the format: /setup <ivle_name>")

##### Error logging and other functions ##########

def cancel(bot, update):
    update.message.reply_text("Okay, operation cancelled.")
    return ConversationHandler.END

def error(bot, update, error):
    """Log errors caused by updates"""
    logger.warning('Update "%s" caused an error "%s"', update, error)

################################
####### Main function ##########
################################

def main():
    """Start the bot"""
    # Create an event handler
    updater = Updater("730332553:AAHBPADd7S43Vn5bPwd0JBVvlTKoY1au_xc")

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('start', start_info))
    dp.add_handler(CommandHandler('setup_sheet', setup_sheet, pass_args=True))
    dp.add_handler(CommandHandler('start_session', start_session, pass_args=True))
    dp.add_handler(CommandHandler('stop_session', stop_session))
    dp.add_handler(CommandHandler('attend', indicate_attendance, pass_args=True))
    dp.add_handler(CommandHandler('setup', setup_student, pass_args=True))

    # Register an error logger
    dp.add_error_handler(error)

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__=="__main__":
    main()
