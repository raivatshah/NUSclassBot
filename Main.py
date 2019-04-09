#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" NUS ClassBot v1.1 
developed using Telegram's BOT API (python v3)

Developers:
Advay Pal 
Chaitanya Baranwal 
Raivat Shah 
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
TOKEN_MAP = "TOKEN_MAP"

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
redis_pickle_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=False)

####################################
#### Google Sheets Commands ########
####################################

#(TODO): Need to store api token in db, not pickle file
def get_service(bot, update, user_id, token=None):
    """Shows basic usage of the Sheets API.
        Prints values from a sample spreadsheet.
        """
    creds = None
    
    if redis_client.hexists(user_id, "credentials"):
        creds = pickle.loads(redis_pickle_client.hget(user_id, "credentials"))

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
            redis_pickle_client.hset(user_id, "credentials", pickle.dumps(creds))

    service = build("sheets", "v4", credentials=creds)
    return service


def create_sheet(bot, update, user_id, token=None):
    """Shows basic usage of the Sheets API.
    Create a new sample spreadsheet.
    """
    service = get_service(bot, update, user_id, token)

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
    redis_client.hset(user_id, "spreadsheet_id", spreadsheet_id)

##############################
##### Bot framework ##########
##############################

##### Tutor ##########    

def setup_sheet(bot, update, args):
    user_id = get_user_id_or_username(bot, update)
    # if not redis_client.exists(user_id):
    #     update.message.reply_text("Invalid command")
    #     return 
    # (TODO): Check if sheet already set up?
    try:
        create_sheet(bot, update, user_id, args[0])
    except:
        create_sheet(bot, update, user_id)
    update.message.reply_text("Sheet successfully created!")

def generate_hash(user_id):
    token = hash(time.time()) % 100000000
    redis_client.hset(TOKEN_MAP, token, user_id)
    return token

def start_session(bot, update, args):
    if len(args) != 1:
        update.message.reply_text("Invalid number of arguments")
        return
    number_of_students = int(args[0])
    if number_of_students <= 0:
        update.message.reply_text("Invalid argument. Cannot have 0 or fewer students")
        return
    user_id = get_user_id_or_username(bot, update)
    if not redis_client.exists(user_id):
        update.message.reply_text("Invalid command")
        return
    elif redis_client.hexists(user_id, "session_started"):
        message = "A session is already running"
    else:
        token = generate_hash(user_id)
        redis_client.hmset(user_id, {
            "session_started": 1,
            "num_students": number_of_students,
            "session_token": token,
            "present_students": json.dumps({})
        })
        message = f"Session Started! Token = {token}"
    update.message.reply_text(message)


def stop_session(bot, update):
    user_id = get_user_id_or_username(bot, update)
    if not redis_client.exists(user_id):
        update.message.reply_text("Invalid command")
        return
    elif not redis_client.hexists(user_id, "session_started"):
        message = "No session running"
    else:
        present_students = json.loads(redis_client.hget(user_id, "present_students"))
        if len(present_students) < int(redis_client.hget(user_id, "num_students")):
            add_values_to_sheet(bot, update, present_students.copy(), redis_client.hget(user_id, "spreadsheet_id"), user_id)
        redis_client.hdel(user_id, "session_started", "session_token", 
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
    user_id = get_user_id_or_username(bot, update)
    if not redis_client.hexists(STUDENT_MAP, user_id):
        update.message.reply_text("You must run /setup before indicating attendance")
        return
    elif len(args) != 1:
        update.message.reply_text("Invalid number of arguments")
        return
    token = int(args[0])
    #(TODO): A student may belong to multiple tutors
    if not redis_client.hexists(TOKEN_MAP, token):
        update.message.reply_text("An error occured, please validate token")
    tutor_id = redis_client.hget(TOKEN_MAP, token)
    update_state(bot, update, user_id, tutor_id)

# (TODO) Retrieve from DB
def get_ivle_name(user_id):
    return redis_client.hget(STUDENT_MAP, user_id)

def update_state(bot, update, user_id, tutor_id):
    num_students = int(redis_client.hget(tutor_id, "num_students"))
    present_students = json.loads(redis_client.hget(tutor_id, "present_students"))
    name = get_ivle_name(user_id)
    if str(user_id) in present_students:
        message = "Attendance already marked!"
    elif num_students == len(present_students):
        message = "Attendance quota filled! Please contact tutor"
    else:
        present_students[user_id] = name
        redis_client.hset(tutor_id, "present_students", json.dumps(present_students))
        message = "Attendance marked!"
        if num_students == len(present_students):
            add_values_to_sheet(bot, update, present_students.copy(), redis_client.hget(tutor_id, "spreadsheet_id"), tutor_id)
    update.message.reply_text(message)

@run_async
def add_values_to_sheet(bot, update, user_ids, spreadsheet_id, tutor_id):
    values = [[name.upper(), "1"] for name in user_ids.values()]
    values = sorted(values, key = lambda x : x[0])
    body = {
        "values": values
    }
    # Call the Sheets API
    service = get_service(bot, update, tutor_id)
    # (TODO): Might fail
    result = service.spreadsheets().values().append(
    spreadsheetId=spreadsheet_id, range="A2:B", 
    valueInputOption="RAW", body=body).execute()

def get_user_id_or_username(bot, update):
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    if redis_client.hexists(STUDENT_MAP, user_id):
        return user_id
    elif username and redis_client.hexists(STUDENT_MAP, username):
        return username
    else:
        return user_id

def setup_student(bot, update, args):
    if len(args) > 0:
        user_id = update.message.from_user.id
        ivle_name = ' '.join(args)
        redis_client.hset(STUDENT_MAP, user_id, ivle_name)
        update.message.reply_text("You have been registered! Please wait " + 
                                    "for your tutor to give you a token")
    else:
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
    updater = Updater(os.environ.get('TELEKEY')) #API key 

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
