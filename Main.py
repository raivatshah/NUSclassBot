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

import telegram
import logging
import os
import pickle
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pyivle

################################################
## Variables required to run program properly ##
################################################

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)
ECHO = range(0)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SAMPLE_LIST = ['Chaitanya Baranwal', 'Raivat Shah', 'Advay Pal']
PICKLE_FILE = 'token.pickle'
STATE_OBJECT = {
    "@advaypal": {
        'token': None,
        'session_started': False
    }
}

####################################
#### Google Sheets Commands ########
####################################

def get_service():
    """Shows basic usage of the Sheets API.
        Prints values from a sample spreadsheet.
        """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists():
        with open(PICKLE_FILE, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(PICKLE_FILE, 'wb') as token:
            pickle.dump(creds, token)

    service = build('sheets', 'v4', credentials=creds)
    return service

def create_sheet():
    """Shows basic usage of the Sheets API.
    Create a new sample spreadsheet.
    """
    service = get_service()

    #(TODO): Sheet might already exist
    # Call the Sheets API
    spreadsheet = {
        'properties': {
            'title': 'NUSClassSample.xlsx'
        }
    }
    spreadsheet = service.spreadsheets().create(body=spreadsheet,
                                        fields='spreadsheetId').execute()
    spreadsheetId = spreadsheet.get('spreadsheetId')
    with open(PICKLE_FILE, 'w') as token:
        pickle.dump({'id': spreadsheetId}, token)

# def add_values_to_sheet(time):
#     values = []
#     for name in SAMPLE_LIST:
#         values.append([name, time])

#     body = {
#         'values': values
#     }

#     # Call the Sheets API
#     service = get_service()
#     spreadsheet = {
#         'properties': {
#             'title': 'NUSClassSample.xlsx'
#         }
#     }
#     spreadsheetId = service.spreadsheets().create(body=spreadsheet,
#                                         fields='spreadsheetId').execute().get('spreadsheetId')

#     result = service.spreadsheets().values().update(
#         spreadsheetId=spreadsheetId, range='A2:B', 
#         valueInputOption='RAW', body=body).execute()

#     print('{0} cells updated.'.format(result.get('updatedCells')))

##############################
##### Bot framework ##########
##############################

##### Tutor ##########    

def setup_sheet(bot, update):
    username = update.message.from_user.username
    if username not in STATE_OBJECT:
        update.message.reply_text("Invalid command")
        return 
    # (TODO): Check if sheet already set up?
    create_sheet()
    update.message.reply_text("Sheet successfully created!")


def generate_hash():
    return 5

def start_session(bot, update, args):
    number_of_students = int(args[0])
    username = update.message.from_user.username
    if username not in STATE_OBJECT:
        update.message.reply_text("Invalid command")
        return
    session_started = STATE_OBJECT[username]['session_started']
    if session_started:
        message = "A session is already running"
    else:
        STATE_OBJECT[username]['session_started'] = True
        STATE_OBJECT[username]['session_token'] = generate_hash()
        message = "Session Started!"
    update.message.reply_text(message)


def stop_session(bot, update, args):
    number_of_students = int(args[0])
    username = update.message.from_user.username
    if username not in STATE_OBJECT:
        update.message.reply_text("Invalid command")
        return
    session_started = STATE_OBJECT[username]['session_started']
    if not session_started:
        message = "No session running"
    else:
        STATE_OBJECT[username]['session_started'] = False
        STATE_OBJECT[username]['session_token'] = None
        message = "Session Stopped"
    update.message.reply_text(message)

##### Student ##########

def add_value_to_sheet(name):
    pass

def indicate_attendance(bot, update, args):
    username = update.message.from_user.username
    if len(args) != 1:
        update.message.reply_text("Invalid number of arguments")
        return
    token = int(args[0])
    for tutor in STATE_OBJECT:
        if tutor['session_token'] == token:
            add_value_to_sheet(username)
            # (TODO): Verify with student count
            update.message.reply_text("Attendance marked!")
            return
    update.message.reply_text("An error occured, please validate token")

def error(bot, update, error):
    """Log errors caused by updates"""
    logger.warning('Update "%s" caused an error "%s"', update, error)

#############################
####### IVLE Login ##########
#############################

def login(): 
    # Authenticate 
    p = pyivle.Pyivle("DubSaHUcwQXbD2F0PH9VI")
    p.login(USER_ID, PASSWORD)

    # Get name and user IDs
    student = p.profile_view() 
    studentName = student.Results[0].Name
    studentID = student.Results[0].UserID

    ## add studentName and studentID to method that adds to the database.

def main():
    """Start the bot"""
    
    # Create an event handler
    updater = Updater('730332553:AAHBPADd7S43Vn5bPwd0JBVvlTKoY1au_xc')

    # Get dispatcher to register handlers
    dp = updater.dispatcher

    # Register different commands
    dp.add_handler(CommandHandler('setup_sheet', setup_sheet))
    dp.add_handler(CommandHandler('start_session', start_session))
    dp.add_handler(CommandHandler('stop_session', stop_session))
    dp.add_handler(CommandHandler('attend', indicate_attendance))
    # dp.add_handler(CommandHandler('help', help_func))

    # Register an error logger
    dp.add_error_handler(error)

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__=='__main__':
    main()