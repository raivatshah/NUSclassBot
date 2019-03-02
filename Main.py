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
import time
import telegram
import logging
import os
import pickle
import urllib.request
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from oauth2client import client
from oauth2client import tools
import random 
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
SAMPLE_LIST = ['Chaitanya Baranwal', 'Raivat Shah', 'Advay Pal']
PICKLE_FILE = 'token.pickle'

TUTOR_OBJECT = {
    "chaitanyabaranwal": {
        "session_started": False,
    },
    "advaypal": {
        "session_started": False,
    }
}

STUDENT_OBJECT = {
    "chaitanyabaranwal" : "Chaitanya Baranwal"
}

####################################
#### Google Sheets Commands ########
####################################

def get_service(bot, update, token=None):
    """Shows basic usage of the Sheets API.
        Prints values from a sample spreadsheet.
        """
    creds = None
    
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(PICKLE_FILE):
        with open(PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)

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
            with open(PICKLE_FILE, "wb") as token:
                pickle.dump(creds, token)

    service = build("sheets", "v4", credentials=creds)
    return service


def create_sheet(bot, update, username, token=None):
    """Shows basic usage of the Sheets API.
    Create a new sample spreadsheet.
    """
    service = get_service(bot, update, token)

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
    TUTOR_OBJECT[username]["spreadsheet_id"] = spreadsheet_id

##############################
##### Bot framework ##########
##############################

##### Tutor ##########    

def setup_sheet(bot, update, args):
    username = update.message.from_user.username
    if username not in TUTOR_OBJECT:
        update.message.reply_text("Invalid command")
        return 
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
    if username not in TUTOR_OBJECT:
        update.message.reply_text("Invalid command")
        return
    tutor_object = TUTOR_OBJECT[username]
    session_started = tutor_object["session_started"]
    if session_started:
        message = "A session is already running"
    else:
        tutor_object["session_started"] = True
        token = generate_hash()
        tutor_object["session_token"] = token
        tutor_object["num_students"] = number_of_students
        tutor_object["present_students"] = {}
        message = f"Session Started! Token = {token}"
    update.message.reply_text(message)


def stop_session(bot, update):
    username = update.message.from_user.username
    if username not in TUTOR_OBJECT:
        update.message.reply_text("Invalid command")
        return
    tutor_object = TUTOR_OBJECT[username]
    session_started = tutor_object["session_started"]
    if not session_started:
        message = "No session running"
    else:
        present_students = tutor_object["present_students"]
        if len(present_students) < tutor_object["num_students"]:
            add_values_to_sheet(bot, update, present_students.copy(), tutor_object["spreadsheet_id"])
        tutor_object["session_started"] = False
        del tutor_object["session_token"]
        del tutor_object["num_students"]
        del tutor_object["present_students"]
        message = "Session Stopped"
    update.message.reply_text(message)

##### Student ##########
def indicate_attendance(bot, update, args):
    username = update.message.from_user.username
    if len(args) != 1:
        update.message.reply_text("Invalid number of arguments")
        return
    token = int(args[0])
    #(TODO): A student may belong to multiple tutors
    for _, tutor_object in TUTOR_OBJECT.items():
        if "session_token" in tutor_object and tutor_object["session_token"] == token:
            update_state(bot, update, username, tutor_object)
            return
    update.message.reply_text("An error occured, please validate token")

# (TODO) Retrieve from DB
def get_ivle_name(username):
    return STUDENT_OBJECT[username]

def update_state(bot, update, username, tutor_object):
    num_students = tutor_object["num_students"]
    present_students = tutor_object["present_students"]
    name = get_ivle_name(username)
    if username in present_students:
        message = "Attendance already marked!"
    elif num_students == len(present_students):
        message = "Attendance quota filled! Please contact tutor"
    else:
        present_students[username] = name
        message = "Attendance marked!"
        if num_students == len(present_students):
            add_values_to_sheet(bot, update, present_students.copy(), tutor_object["spreadsheet_id"])
    update.message.reply_text(message)

@run_async
def add_values_to_sheet(bot, update, usernames, spreadsheet_id):
    values = [[username, "1"] for username in usernames.values()]
    body = {
        "values": values
    }
    # Call the Sheets API
    service = get_service(bot, update)
    # (TODO): Might fail
    result = service.spreadsheets().values().append(
    spreadsheetId=spreadsheet_id, range="A2:B", 
    valueInputOption="RAW", body=body).execute()

def setup_student(bot, update):
    update.message.reply_text("Okay! Please enter your name as registered on IVLE.")
    return INPUT_NAME

def input_name(bot, update):
    STUDENT_OBJECT[update.message.from_user.username] = update.message.text
    update.message.reply_text("Okay! You have been registered.")
    return ConversationHandler.END

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
    load_data_from_file()
    # Create an event handler
    updater = Updater("730332553:AAHBPADd7S43Vn5bPwd0JBVvlTKoY1au_xc")

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('setup_sheet', setup_sheet, pass_args=True))
    dp.add_handler(CommandHandler('start_session', start_session, pass_args=True))
    dp.add_handler(CommandHandler('stop_session', stop_session))
    dp.add_handler(CommandHandler('attend', indicate_attendance, pass_args=True))
    student_name_handler = ConversationHandler(
        entry_points = [CommandHandler('setup', setup_student)],
        states = {
            INPUT_NAME: [MessageHandler(Filters.text, input_name)]
        },
        fallbacks = [CommandHandler('cancel', cancel)],
        conversation_timeout = 10.0,
    )
    dp.add_handler(student_name_handler)

    # Register an error logger
    dp.add_error_handler(error)

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

def load_data_from_file():
    pass

def save_to_file():
    pass

if __name__=="__main__":
    main()