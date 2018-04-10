from __future__ import print_function
import httplib2
import os
import base64
import email
import datetime
import sys


from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools
from email.mime.text import MIMEText
from string import ascii_lowercase
from time import strftime
from time import sleep

from apiclient.http import MediaFileUpload

from random import randint

import logging

from peewee import *


from apiclient import errors

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

SCOPES = 'https://mail.google.com/ https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'SNP Automated Reservation System'

DB_path = ""
PROD = True
Linux_home_dir = ('/mraaz')

if sys.platform.startswith('linux'):  # linux
    if not os.path.exists(Linux_home_dir):
        os.makedirs(Linux_home_dir)

    logging.basicConfig(filename= Linux_home_dir + '/debug_SNPARS.log', level=logging.CRITICAL, format='%(asctime)s - %(message)s')

    if PROD:
        DB_path = os.path.join(Linux_home_dir,
                                   'SNPARS.db')

    else:
        DB_path = os.path.join(Linux_home_dir,
                                   'Test.db')

elif sys.platform == "win32": # Windows...
#if system is Windows run from current directory
    logging.basicConfig(filename= os.getcwd() + '\debug_SNPARS.log', level=logging.CRITICAL, format='%(asctime)s - %(message)s')
    if PROD:
        DB_path = os.path.join(os.getcwd(),
                                   'SNPARS.db')
    else:
        DB_path = os.path.join(os.getcwd(),
                                   'Test.db')
        #logging.critical ("Windows")


DATABASE = DB_path
DEBUG = True


Events_frequency = 3 #Next game to be scheduled in weeks
Number_of_events_scheduled = 10  #Number of games to be auto added. Remember the GrandFinal needs to be done manually so don't do too much plus we have a break in Dec

__SNP_From_Address__ = 'snpbrisbane@gmail.com'

__SNP_Subject__ = 'SNP Automated Reserve System!'


__strUsageMsg__ = 'Please reply back with the following number/s in the Email Body\n\n' \
               '1 - Accept Invite to the latest SNP\n' \
               '2 - Decline an already accepted invite\n' \
               '3 - Get details for next SNP Event\n' \
               '4 - Get current attendance for next SNP\n' \
               '5 - List of all upcoming SNP games\n' \
               '42 - Unsubscribe from SNP\n\n' \
               'For example you can send the following in the email body to get details and attendance:  3, 4'

__SNP_WelcomeMsg__ = "Welcome to SNP Automated Reserve System.\n\n" \
                     "Instructions are simple, this system accepts certain commands by scanning the 1st line of the email body.\n\n" \
                     "Every 3 weeks a game is scheduled and an email will be sent out to all registered members.\n\n" \
                     "Have fun and enjoy, any questions please email Marc Raaz @ mnraaz@gmail.com.\n\n" + __strUsageMsg__


__MAX_Players_Invited__ = 10 # Number of people before they start going to Reservation list

__SNP_Invite_Body__ = "Hi All\n\n" \
                      "Invites out!\n\n" \
                      "Details for the night are:\n\n" \
                      "Date: See the email subject for the date.\n\n" \
                      "Time: 6.45pm for 7.00 pm start.\n\n" \
                      "Bonus: On time arrivals will receive approximately 10% extra chips.\n\n" \                      
                      "Drinks: BYO.\n\n" \
                      "Please RSVP by 7:00 PM Wednesday prior to game night.\n\n" \
                      "Invite-a-friend: Please invite your friends. Just ask them to send an email to " + __SNP_From_Address__ + " with only 'SNP' (no quotes) in the body or subject of the email to register.\n\n" \
                      "Invites out: Invites goes out randomly between 3pm and 6:30pm on Game nights, only the 1st 9 people will be accepted the remaining will go on the waiting list. (10th spot is for new arrivals...aka fresh blood)\n\n" \
                      "Auto Replies: This is frowned upon and very easily detected, please refrain from doing this, repeated offenders will be dealt with accordingly\n\n" \
                     
__SNP_Declined_Email__ = "Why thank you my good sir, I will send out invites to the other good folks at once.\n"

__SNP_Accepted_Email__ = "Congratulations, you're in!\n\n" \
                         "A calendar entry has been created.\n\n" \
                         "You're number "

__SNP_Reserve_Email__ = "Unfortunately we're full.\n\n" \
                        "You have been placed in the Reserve list and are currently number  "

__SNP_Reserve_Available_Email__ = "Heya!\n\n" \
                                  "A spot has just opened up for the next SNP invite.\n\n" \
                                  "Please reply back with 1 in the email body to accept the invite.\n\n"

__SNP_No_Games_Msg__ = "No games organised but you're in the system, we will email you when the next game is scheduled."

__SNP_Admin_Usage_Msg__ = "100 creates a game based on info in the Subject: eg SNP 01 12 2015 (This will create a game for the 1 Dec 2015)\n\n" \
                          "101 will delete the Game ID specificed in the Subject, based on 6 - List of all upcoming SNP games\n\n" \
                          "102 will update the Game ID specificed in the Subject to be the Final Game (Not the Grand Final) - 1 for True, 2 for False, based on 6 - List of all upcoming SNP games eg Subject = 1 1 Body = 102"

__SNP_Cancelled_Msg__ = "Sorry guys but the latest SNP Game has been cancelled...or has it??\n\n" \
                        "This is a automated email so it's very likely that this email might also get cancelled, meaning its bogus.\n\n" \
                        "Confusing I know, imagine how I feel\n\n" \
                        "Marc Raaz the human should sent out an email shortly verifying if indeed the next SNP has been cancelled."

__SNP_Location__ = "t " \
                   "Brisbane"

# create a peewee database instance -- our models will use this database to
# persist information
sqlite_db = SqliteDatabase(DATABASE)

# model definitions -- the standard "pattern" is to define a base model class
# that specifies which database to use.  then, any subclasses will automatically
# use the correct storage.
class BaseModel(Model):
    class Meta:
        database = sqlite_db

# Because we have not specified a primary key, peewee will automatically
# add an auto-incrementing integer primary key field named id.

class Events(BaseModel):
    date_expiry_time = DateTimeField(unique=True)
    sentFlag = BooleanField(default=False)
    FinalGamefortheYear = BooleanField(default=False)

class Player(BaseModel):
    name = CharField()
    email = CharField(unique=True)
    ban_list = BooleanField(default=False)

class Reservations(BaseModel):
    playerID = ForeignKeyField(Player)
    eventsID = ForeignKeyField(Events)
    join_date = DateTimeField(null=True)
    expiry_time = DateTimeField(null=True)
    sentFlag = BooleanField(default=False)

class GuestList(BaseModel):
    playerID = ForeignKeyField(Player)
    eventsID = ForeignKeyField(Events)

class Utility(BaseModel):
    random_time = IntegerField()

def create_tables():
    sqlite_db.connect()
    sqlite_db.create_tables([Player, Events, Reservations, GuestList, Utility], True)

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """

    """ Removed Gmail's OG script to store creds elsewhere
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    """
    if sys.platform.startswith('linux'):  # linux
        #logging.critical ("Linux")
        if not os.path.exists(Linux_home_dir):
            os.makedirs(Linux_home_dir)

        if PROD:
            credential_path = os.path.join(Linux_home_dir,
                                   'gmail-python-SNPARS.json')
        else:
            credential_path = os.path.join(Linux_home_dir,
                                   'gmail-mnraaz-test.json')

    elif sys.platform == "darwin": # OS X
        logging.critical ("OS X")
    elif sys.platform == "win32": # Windows...
        #if system is Windows run from current directory

        if PROD:
            credential_path = os.path.join(os.getcwd(),
                                   'gmail-python-SNPARS.json')
        else:
            credential_path = os.path.join(os.getcwd(),
                                       'gmail-mnraaz-test.json')
        #logging.critical ("Windows")


    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        logging.critical('Storing credentials to ' + credential_path)
    return credentials

def GetMimeMessage1stLine(service, user_id, msg_id):
  """Get a Message and use it to create a MIME Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The ID of the Message required.

  Returns:
    A MIME Message, consisting of data from Message.
  """
  try:
    message = service.users().messages().get(userId=user_id, id=msg_id,
                                             format='raw').execute()

    #logging.critical ('Message snippet: %s' % message['snippet'])

    msg_str = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))

    mime_msg = email.message_from_string(msg_str)

    body = ""

    if mime_msg.is_multipart():
        for part in mime_msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))

        # skip any text/plain (txt) attachments
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                body = part.get_payload(decode=True)  # decode
                break
    # not multipart - i.e. plain text, no attachments, keeping fingers crossed
    else:
        body = mime_msg.get_payload(decode=True)


    #logging.critical (body)
    # Did rstrip as \r was coming in from email and messing up the .get in my dictionary also removed \r\n
    # Nice read about why: http://programmers.stackexchange.com/questions/29075/difference-between-n-and-r-n

    strSplitintoLines = str(body).strip().replace("\r", "")
    test = strSplitintoLines.split('\n')
    return (test[0])

  except errors.HttpError, error:
    return ""

def GetMessage(service, user_id, msg_id):
  """Get a Message with given ID.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The ID of the Message required.

  Returns:
    A Message.
  """
  try:
    message = service.users().messages().get(userId=user_id, id=msg_id).execute()

    #logging.critical ('Message snippet: %s' % message['snippet'])

    return message['snippet']
  except errors.HttpError, error:
    logging.critical ('An error occurred in GetMessage: %s' % error)

def ModifyMessage(service, user_id, msg_id, msg_labels):
  """Modify the Labels on the given Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The id of the message required.
    msg_labels: The change in labels.

  Returns:
    Modified message, containing updated labelIds, id and threadId.
  """
  try:
    message = service.users().messages().modify(userId=user_id, id=msg_id,
                                                body=msg_labels).execute()

    label_ids = message['labelIds']

    #logging.critical ('Message ID: %s - With Label IDs %s' % (msg_id, label_ids))
    #return message
  except errors.HttpError, error:
    logging.critical('An error occurred in ModifyMessage: %s' % error)

def SendMessage(service, user_id, message):
  """Send an email message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

  Returns:
    Sent Message.
  """
  try:
    message = (service.users().messages().send(userId=user_id, body=message)
               .execute())
    #logging.critical ('Message Id: %s' % message['id'])
    return message
  except errors.HttpError, error:
    logging.critical ('An error occurred in SendMessage: %s' % error)


def CreateMessage(sender, to, subject, message_text):
  """Create a message for an email.

  Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

  Returns:
    An object containing a base64 encoded email object.
  """
  message = MIMEText(message_text)
  message['from'] = sender
  message['to'] = to
  message['subject'] = subject
  return {'raw': base64.urlsafe_b64encode(message.as_string())}


def strip_string_to_lowercase(s):
  return filter(lambda x: x in ascii_lowercase, s.lower())

def getNextEventID():
    return Events.select(Events.id).order_by(Events.date_expiry_time.asc()).limit(1)

def checkNextEventID():
    if (Events.select().count()) > 0:
        return True
    else:
        return False

def getSingleEmailfromSQLstring(strSQL):

    myMsg2 = ""

    try:
        for stupid in Player.select(Player.email).where(Player.id == strSQL):
            myMsg2 = stupid.email
    except ValueError:
        pass

    if myMsg2 == "":
        sys.exit(0)

    return myMsg2

# def random_date(start, end):
#     """
#     This function will return a random datetime between two datetime
#     objects. (http://stackoverflow.com/questions/553303/generate-a-random-date-between-two-other-dates)
#     """
#     delta = end - start
#     int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
#     random_second = randrange(int_delta)
#     return start + datetime.timedelta(seconds=random_second)


def usageOne(playerID):
    """
    :param playerID:
    :return: 1 - Accept Invite to the latest SNP
    """
    if DEBUG:
        logging.critical ("Got to 1")

    if DEBUG:
        logging.critical ("Got to 1a")

    myMsg = ""
    format = "%d %b %Y"

    for listofEvents in Events.select().where(Events.id == getNextEventID()):
        myMsg = listofEvents.date_expiry_time.strftime(format)

    #new_guests = Reservations()
    #people = new_guests.select()
    #logging.critical ("Number of new_guests  in database %s" % people.count())
    #for user in people:
    #    user.delete_instance()
    #logging.critical (people.count())

    # Check if space is available if available
    # pop in otherwise add to reservation
    green_light = GuestList.select().count()
    myMsg2 = getSingleEmailfromSQLstring(playerID)

    # Check if there even is a next party
    if not checkNextEventID():
        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, 'No games scheduled, please wait for an invite'))
        if DEBUG:
            logging.critical ("Got to 1x")
        return

    if (GuestList.select().join(Player).where(Player.id == playerID, GuestList.eventsID == getNextEventID()).count()) != 0: # Comfirm player doesn't already exist
        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, 'Your are already in bro!'))
        if DEBUG:
            logging.critical ("Got to 1b")
        return

    #logging.critical(" in 1b")
    if green_light < __MAX_Players_Invited__:
        if Events.select().order_by(Events.date_expiry_time.asc()).count() == 0:
            SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, __SNP_No_Games_Msg__)) #No Games message but sending an ack so they know it didn't get ingnored
            if DEBUG:
                logging.critical ("Got to 1c")
        else:
            update_player = GuestList(eventsID = getNextEventID(), playerID = playerID )
            update_player.save()
            SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__ + ' - ' + myMsg, __SNP_Accepted_Email__ + str(green_light + 1))) #Accepted email
            updateCalendarEvent(myMsg2)

            if DEBUG:
                logging.critical ("Got to 1d")

            #Now need to check if the player was in the Reservation list, if so lets now delete them
            for x in Reservations.select().where(Reservations.playerID == playerID):
                x.delete_instance(True)

    else:
        # Add to reserve list
        # Make sure it doesn't exist
        # Add to table
        if DEBUG:
            logging.critical ("Got to 1e")
        if (Reservations.select().where(Reservations.playerID == playerID, Reservations.eventsID == getNextEventID()).count()) == 0:
            q = Reservations(playerID = playerID, eventsID = getNextEventID(), join_date = datetime.datetime.today())
            q.save()
            reservation_number_in_list = Reservations.select().count()
            SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, __SNP_Reserve_Email__ + str(reservation_number_in_list)))
            if DEBUG:
                logging.critical ("Got to 1f")

    if DEBUG:
        logging.critical ("Got to 1g")

    return

def usageTwo(playerID):
    """
    :param playerID: Player ID
    :return: 2 - Decline an already accepted invite
			 Kick off process to email invite to the next reserved member
    """
    if DEBUG:
        logging.critical ("Got to 2")
    myMsg2 = getSingleEmailfromSQLstring(playerID)


    if (GuestList.select().join(Player).where(Player.id == playerID).count()) == 0: # Comfirm player is invited
        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, "Sorry you don't have any accepted games at this stage, we can ONLY decline accepted players."))
        if DEBUG:
            logging.critical ("Got to 2a")
        return
    else:
        for user in GuestList.select().join(Player).where(Player.id == playerID):
            deleteAttendess(myMsg2)
            user.delete_instance()
            if DEBUG:
                logging.critical ("Got to 2b")

        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, __SNP_Declined_Email__))
        if DEBUG:
            logging.critical ("Got to 2c")

    # # Find the next person on the reserve list
    # # Delete them from the table and send them an invite
    # if Reservations.select().count() > 0:
    #     #nextPlayer = Reservations.select(Player.id).join(Player).order_by(Reservations.join_date.asc()).limit(1)
    #     #myMsg2 = getSingleEmailfromSQLstring(nextPlayer)
    #
    #     for nextplayer in Reservations.select().order_by(Reservations.join_date.asc()).limit(1):
    #         myMsg2 = getSingleEmailfromSQLstring(nextplayer.playerID)
    #         nextplayer.expiry_date = getReservationExpiry()
    #         nextplayer.save()
    #         SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, __SNP_Reserve_Available_Email__))

    return

def usageThree(playerID):
    """
    :param playerID:
    :return:  3 - Get details for next SNP Event
    """

    if DEBUG:
        logging.critical ("Got to 3")
    myMsg2 = getSingleEmailfromSQLstring(playerID)

    myMsg = ""
    #format = "%a %b %d %H:%M:%S %Y" # SNP Tue Dec 22 15:13:34 2015 Invite
    format = "%d %b %Y"

    for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()).limit(1):
        myMsg = myMsg + "SNP %s Invite" % listofEvents.date_expiry_time.strftime(format)
        if DEBUG:
            logging.critical ("Got to 3a")

    #logging.critical (myMsg)

    if myMsg == "":
        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, __SNP_No_Games_Msg__))
    else:
        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, myMsg, __SNP_Invite_Body__))

    if DEBUG:
        logging.critical ("Got to 3b")

    return

def usageFour(playerID):
    """
    :param playerID:
    :return: 4 - Get current attendance of next SNP
    """
    if DEBUG:
        logging.critical ("Got to 4a")

    myMsg2 = getSingleEmailfromSQLstring(playerID)

    myMsg = "SNP accepted guest list as follows:\n\n"

    """
    for listofEvents in GuestList.select(GuestList, Player.name.alias('Testing'), Player.email).join(Player, JOIN.INNER).order_by(Player.name):
        if listofEvents.Testing == "":
            myMsg = myMsg + listofEvents.Player.email + "\n"
        else:
            myMsg = myMsg + listofEvents.Player.name + "\n"

    """
    # Couldn't get a join working where GuestList joins to Player to get Player details so created two queries instead :'(

    sq = GuestList.select()
    intcount = 0

    for x in sq:
        if DEBUG:
            logging.critical ("Got to 4b")
        for i in Player.select().where(Player.id == x.playerID):
            intcount += 1
            if DEBUG:
                logging.critical ("Got to 4c")
            if i.name == "":
                myMsg = myMsg + i.email + "\n"
                if DEBUG:
                    logging.critical ("Got to 4d")
            else:
                myMsg = myMsg + i.name + "\n"
                if DEBUG:
                    logging.critical ("Got to 4e")

    #logging.critical(" in 4a")
    if myMsg == "SNP accepted guest list as follows:\n\n":
        myMsg = myMsg + "No players so far :(\nJoin now to be the 1st!" + "\n"

    SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, myMsg + '\n\nTotal number of players: ' + str(intcount)))

    if DEBUG:
        logging.critical ("Got to 4f")

    return

def usageFortyTwo(playerID):
    """
    :param playerID:
    :return: 42 - Unsubscribe from SNP
    """
    if DEBUG:
        logging.critical ("Got to 42")

    if Player.select().where(Player.id == playerID).count() == 0:
        return

    if DEBUG:
        logging.critical ("Got to 42a")

    myMsg2 = getSingleEmailfromSQLstring(playerID)
    SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, 'Sorry to see you leave, Yall come back now! Ya hear?'))

    existingPlayer = Player.select().where(Player.id == playerID)
    for x in existingPlayer:
        x.delete_instance(True)
        if DEBUG:
            logging.critical ("Got to 42b")

    if DEBUG:
        logging.critical ("Got to 42c")

    sys.exit(0)

def usageFive(playerID):
    """
    :param playerID:
    :return: 5 - List of all Upcoming SNP games
    """
    if DEBUG:
        logging.critical ("Got to 5")

    myMsg = "List of SNP games:\n\n"
    format = "%d %b %Y"
    count = 1

    for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()):
        myMsg = myMsg + ("SNP Game '{0}' on '{1}'\n".format(count, listofEvents.date_expiry_time.strftime(format)))
        count += 1
        if DEBUG:
            logging.critical ("Got to 5a")


    myMsg2 = getSingleEmailfromSQLstring(playerID)


    if myMsg == "List of SNP games:\n\n":
       myMsg = "No games scheduled"

    SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, __SNP_Subject__, myMsg))

    if DEBUG:
        logging.critical ("Got to 5b")

def usage100(strSubject, strEmail):
    """
    :param: Email subject and Email Address
    :return: sent date of a new Event(if from xxxx sent to list invite email)
    """
    if DEBUG:
        logging.critical ("Got to 100")

    if (strEmail == 'xxx@gmail.com') or (strEmail == 'xxxx@gmail.com') or (strEmail == 'xxxx@gmail.com'):
        if (strSubject != "") and ((strSubject).lower().find("snp") != -1):
            strMylist = strSubject.split(" ")
            if DEBUG:
                logging.critical ("Got to 100a")

            try:
                eventDate = datetime.datetime(int(strMylist[3]), int(strMylist[2]), int(strMylist[1]), 19, 00, 00)  #ONLY place to set the hours and minutes
                logging.critical (eventDate)
            except IndexError:
                return

            newHappening = Events()
            newHappening.date_expiry_time = eventDate

            try:
                newHappening.save()
            except IntegrityError:
                return

            """ I'm a dumbass but nice to have, following code converts DateTimeField from the DB to DateTime in python
                but for this excerise we don't need it

            myMsg =  Events.select(Events.date_expiry_time).where(Events.id == getNextEventID())
            for x in myMsg:
               strStartTime = datetime.datetime.strptime(str(x.date_expiry_time), "%Y-%m-%d %H:%M:%S")
            logging.critical(strStartTime)
            """

            myMsg = ""
            format = "%d %b %Y %H %M "
            strEmailHeaderDate = eventDate.strftime(format)

            #strEndTime = eventDate + datetime.timedelta(hours=4)
            createCalendarEvent('SNP - ' + strEmailHeaderDate + ' Game', eventDate, (eventDate + datetime.timedelta(hours=4)))


            # Once saved send a list of all events
            myMsg = ""
            count = 1

            for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()):
                myMsg = myMsg + ("SNP Game '{0}' on '{1}'\n".format(count, listofEvents.date_expiry_time.strftime(format)))
                count += 1

            if myMsg == "":
                myMsg = "No games scheduled"

            SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, myMsg))
            return

        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, __SNP_Admin_Usage_Msg__))
        if DEBUG:
            logging.critical ("Got to 100c")



def usage101(strSubject, strEmail):
    """
    :param strSubject:
    :param strEmail:
    :return: From List (item 6) determine game id and send 101 in the body and game id in subject to Delete that game
    """
    if DEBUG:
        logging.critical ("Got to 101")

    if (strEmail == 'xxx@gmail.com') or (strEmail == 'xxxx@gmail.com') or (strEmail == 'xxxx@gmail.com'):
        if DEBUG:
            logging.critical ("Got to 101a")

        if strSubject != "":
            strMylist = strSubject.split(" ")

            try:
                deletethisgame = int(strMylist[0])
                if DEBUG:
                    logging.critical ("Got to 101b")
            except ValueError:
                if DEBUG:
                    logging.critical ("Got to 101c")
                return

            count = 1

            # Grab all events and if the number sent in subject matches; get all the guests and email them
            # Then delete
            for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()):
                if count == deletethisgame:
                    if listofEvents.FinalGamefortheYear != True:
                        for x in GuestList.select().where(GuestList.eventsID == listofEvents.id): #Grab everyone in the guest table for this event
                            for y in Player.select().where(Player.id == x.playerID):
                                SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, __SNP_Cancelled_Msg__))
                                if DEBUG:
                                    logging.critical ("Got to 101d")

                    listofEvents.delete_instance(True)
                    if DEBUG:
                        logging.critical ("Got to 101e")

                    if (listofEvents.id == getNextEventID()):
                        deleteNextCalendarEvent()
                        if DEBUG:
                            logging.critical ("Got to 101f")
                    count += 1
                else:
                    count += 1

            #usageSix() Stupid I know but safes me from changing the method input
            myMsg = ""
            format = "%d %b %Y"
            count = 1

            for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()):
                myMsg = myMsg + ("SNP Game '{0}' on '{1}'\n".format(count, listofEvents.date_expiry_time.strftime(format)))
                count += 1

            if myMsg == "":
                myMsg = "No games scheduled"

            SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, myMsg))
            if DEBUG:
                logging.critical ("Got to 101g")
            return

        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, __SNP_Admin_Usage_Msg__))

    return

def usage102(strSubject, strEmail):
    """
    :param strSubject:
    :param strEmail:
    :return: From List (item 6) determine game id and send 101 in the body and game id in subject to udpdate the game to be the Final Game
    """
    if DEBUG:
        logging.critical ("Got to 102")

    if (strEmail == 'xxx@gmail.com') or (strEmail == 'xxxz@gmail.com') or (strEmail == 'xxxx@gmail.com'):
        if strSubject != "" :
            strMylist = strSubject.split(" ")

            try:
                updatethisgame = int(strMylist[0])
                updateValue = int(strMylist[1])
            except ValueError:
                return

            count = 1

            # Grab all events and if the number sent in subject matches;
            # Then update to  true
            for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()):
                if count == updatethisgame:
                    if updateValue == 1:
                        listofEvents.FinalGamefortheYear = True
                    elif updateValue == 2 :
                        listofEvents.FinalGamefortheYear = False

                    listofEvents.save()
                    count += 1
                else:
                    count += 1

            #usageSix() Stupid I know but safes me from changing the method input
            myMsg = ""
            format = "%d %b %Y"
            count = 1

            for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()):
                myMsg = myMsg + ("SNP Game '{0}' on '{1} and Final Game Flag is '{2}' '\n".format(count, listofEvents.date_expiry_time.strftime(format), listofEvents.FinalGamefortheYear))
                count += 1

            if myMsg == "":
                myMsg = "No games scheduled"

            SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, myMsg))
            return

        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail, __SNP_Subject__, __SNP_Admin_Usage_Msg__))

    return


def createCalendarEvent(strSummary, DateTimeStartDateTime, DateTimeEndDateTime):

    startTime = strftime("%Y-%m-%dT%H:%M:%S+10:00", DateTimeStartDateTime.timetuple())
    endTime = strftime("%Y-%m-%dT%H:%M:%S+10:00", DateTimeEndDateTime.timetuple())
    #endTime = strftime("%Y-%m-%dT%23:00:00+10:00", DateTimeEndDateTime.timetuple())

    if DEBUG:
        logging.critical ("Got to createCalendar")

    #strStartDateTime = (DateTimeStartDateTime).isoformat() + 'Z'  # 'Z' indicates UTC time
    #strEndDateTime = (DateTimeEndDateTime).isoformat() + 'Z'  # 'Z' indicates UTC time

    CalendarEvent = {
        'summary': strSummary,
        'location': __SNP_Location__,
        'description': __SNP_Invite_Body__,
        'start': {
            'dateTime': startTime,
            #'dateTime': '2015-12-27T19:00:00+10:00',
            'timeZone': 'Australia/Brisbane',
        },
        'end': {
            'dateTime': endTime,
            #'dateTime': '2015-12-27T23:00:00+10:00',
            'timeZone': 'Australia/Brisbane',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
            {'method': 'popup', 'minutes': 24 * 60},
            {'method': 'email', 'minutes': 7 * 24 * 60},
            ],
        },
        'guestsCanInviteOthers': False,
    }

    events = calendarService.events().insert(calendarId='primary', body=CalendarEvent).execute()
    if DEBUG:
        logging.critical ("Got to createCalendarA")


def updateCalendarEvent(strEmail):
    """
    We'v decided and this is yet to be tested, that rather than searching the summary
    for the next game, we will ASSUME (yikes!!!) that the next Calendar event is the next
    game. This MEANS that we can't create any entries in this calendar except for ACTUAL games!!!

    Just to be safe I'll do a check for 'SNP - ' in the summary.

    :return:
    """
    if DEBUG:
        logging.critical ("updateCalendarEvent: 1")
    #So since we didn't check summary now we have to add nine hours to make sure that invitations sent out during the game don't get mixed up with the current invite (Since all invites are four hours long)
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).isoformat() + 'Z' # 'Z' indicates UTC time
    #logging.critical('Getting the upcoming 1 event from now based on end time')
    eventsResult = calendarService.events().list(
        calendarId='primary', timeMin=now, maxResults=1, singleEvents=True,
        orderBy='startTime').execute() #CARE maxResults!!!
    events = eventsResult.get('items', [])

    # if not events:
    #     logging.critical("no events")
    # else:
    #     logging.critical ("events")
    # return
    if DEBUG:
        logging.critical ("updateCalendarEvent: 2")
    for event in events:
        if DEBUG:
            logging.critical ("updateCalendarEvent: 2a")
        #start = event['start'].get('dateTime', event['start'].get('date'))
        if str(event['summary']).find("SNP - ") != -1:
            if DEBUG:
                logging.critical ("updateCalendarEvent: 2b")
            #logging.critical(start, event['summary'], event['id'])
            # First retrieve the event from the API.
            events = calendarService.events().get(calendarId='primary', eventId=event['id']).execute()

            #If calendar item was created with no attendees catch that error and create it. (Which is always the case)
            try:
                events['attendees'] = events['attendees'] + [{'email': strEmail}]
                if DEBUG:
                    logging.critical ("updateCalendarEvent: 2c")
            except KeyError:
                events['attendees'] = [{'email': strEmail}]
                if DEBUG:
                    logging.critical ("updateCalendarEvent: 2d")

            if DEBUG:
                logging.critical ("updateCalendarEvent: 2e")
            updated_event = calendarService.events().update(calendarId='primary', eventId=events['id'], sendNotifications=True, body=events).execute()
            if DEBUG:
                logging.critical ("updateCalendarEvent: 2f")

            # Print the updated date.
            #logging.critical (updated_event['updated'])
    if DEBUG:
        logging.critical ("updateCalendarEvent: 3")

def deleteNextCalendarEvent():

    if DEBUG:
        logging.critical ("Got to deleteNextCalendar")
    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=4)).isoformat() + 'Z' # 'Z' indicates UTC time
    #logging.critical('Getting the upcoming 1 event from now based on end time')
    eventsResult = calendarService.events().list(
        calendarId='primary', timeMin=now, maxResults=1, singleEvents=True,
        orderBy='startTime').execute()
    CalendarEvents = eventsResult.get('items', [])

    # if not events:
    #     logging.critical("no events")
    # else:
    #     logging.critical ("events")
    # return

    for CalendarEvent in CalendarEvents:
        #start = event['start'].get('dateTime', event['start'].get('date'))
        if str(CalendarEvent['summary']).find("SNP - ") != -1:
            #logging.critical(start, event['summary'], event['id'])
            calendarService.events().delete(calendarId='primary', eventId=CalendarEvent['id']).execute()

def deleteAllFutureCalendarEvents():
    """
    This method is to clean up the calendar and not to confuse the poor guy

    :return:
    """

    if DEBUG:
        logging.critical ("Got to deleteAllFutureCalendarEvents")

    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=4)).isoformat() + 'Z' # 'Z' indicates UTC time
    #logging.critical('Getting the upcoming 1 event from now based on end time')
    eventsResult = calendarService.events().list(
        calendarId='primary', timeMin=now, maxResults=100, singleEvents=True,
        orderBy='startTime').execute()
    CalendarEvents = eventsResult.get('items', [])

    # if not events:
    #     logging.critical("no events")
    # else:
    #     logging.critical ("events")
    # return

    for CalendarEvent in CalendarEvents:
        calendarService.events().delete(calendarId='primary', eventId=CalendarEvent['id']).execute()


def deleteAttendess(strEmail):
    """
    This method is to delete 1 person from the calendar invite.

    :return:
    """

    if DEBUG:
        logging.critical ("Got to deleteAttendess")

    now = (datetime.datetime.utcnow() + datetime.timedelta(hours=4)).isoformat() + 'Z' # 'Z' indicates UTC time
    #logging.critical('Getting the upcoming 1 event from now based on end time')
    eventsResult = calendarService.events().list(
        calendarId='primary', timeMin=now, maxResults=1, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    # if not events:
    #     logging.critical("no events")
    # else:
    #     logging.critical ("events")
    # return
    for event in events:
        #start = event['start'].get('dateTime', event['start'].get('date'))
        if str(event['summary']).find("SNP - ") != -1:
            #logging.critical(start, event['summary'], event['id'])
            #logging.critical("got here")
            # First retrieve the event from the API.
            events = calendarService.events().get(calendarId='primary', eventId=event['id']).execute()

            #If calendar item was created with no attendees catch that error and create it. (Which is always the case)
            myStr = ""
            newList = []
            if DEBUG:
                logging.critical("Got to deleteAttendess 1a")
            try:

                for x in events['attendees']:
                    logging.critical("email addy is: " + x['email'] + " and the strEmail addy is: " + strEmail)
                    myStr = x.get('email')
                    if myStr != strEmail:
                        newList.append(myStr)
                        if DEBUG:
                            logging.critical("Email addy added to the newList")
                    #if (x['email'].find(strEmail)) == 1:
                    #    logging.critical ("Got here")
                        #myStr += {'email': x['email']}

                    #    if DEBUG:
                    #        logging.critical ("Got to deleteAttendess 1b")

                del events['attendees']
                stupidFUCKEN1stpassfix = True
                for trythis in newList:
                    if stupidFUCKEN1stpassfix:
                        events['attendees'] = [{'email': trythis }]
                        stupidFUCKEN1stpassfix = False
                    else:
                        events['attendees'] = events['attendees'] + [{'email': trythis }]
                if DEBUG:
                    logging.critical ("Got to deleteAttendess 1d")

            except KeyError:
                if DEBUG:
                    logging.critical ("Got to deleteAttendess 1e")
                return
            #logging.critical (events['attendees'].index(["email", "test@test.com"]))
            #events['attendees'] = events['attendees'].remove(strEmail)
            #except KeyError:
                #events['attendees'] = [{'email': strEmail}]

            updated_event = calendarService.events().update(calendarId='primary', eventId=events['id'], sendNotifications=True, body=events).execute()

            # Print the updated date.
            if DEBUG:
                logging.critical (updated_event['updated'])
                logging.critical ("WOOOOORKF!!!!")


def clean_house():

    backupDB()

    Player.drop_table(True)
    Events.drop_table(True)
    Reservations.drop_table(True)
    GuestList.drop_table(True)
    Utility.drop_table(True)

    deleteAllFutureCalendarEvents()


def backupDB(): #service, title, description, parent_id, mime_type, filename):
  """Insert new file.

  Args:
    service: Drive API service instance.
    title: Title of the file to insert, including the extension.
    description: Description of the file to insert.
    parent_id: Parent folder's ID.
    mime_type: MIME type of the file to insert.
    filename: Filename of the file to insert.
  Returns:
    Inserted file metadata if successful, None otherwise.
  """

  if DEBUG:
    logging.critical ("Got to backupDB")

  media_body = MediaFileUpload(DATABASE, mimetype='application/x-sqlite3', resumable=True)


  #media_body = MediaFileUpload(filename, mimetype=mime_type, resumable=True)
  # body = {
  #   'title': title,
  #   'description': description,
  #   'mimeType': mime_type
  # }

  if PROD:
      body = {
        'name': 'SNPARS.db - ' + str(datetime.datetime.today()),
        'description': 'test description',
        'mimeType': 'application/x-sqlite3'
      }
  else:
      body = {
        'name': 'Test.db - ' + str(datetime.datetime.today()),
        'description': 'test description',
        'mimeType': 'application/x-sqlite3'
      }
  try:
    file = driveService.files().create(body=body,media_body=media_body).execute()

  except errors.HttpError, error:
    logging.critical ('An error occured: %s' % error)
  # Set the parent folder.
  #if parent_id:
  #  body['parents'] = [{'id': parent_id}]
  #
  # try:
  #   file = driveService.files().insert(
  #       body=body,
  #       media_body=media_body).execute()
  #
  #   # Uncomment the following line to logging.critical the File ID
  #   # logging.critical 'File ID: %s' % file['id']
  #
  #   return file
  # except errors.HttpError, error:
  #   logging.critical ('An error occured: %s' % error)
  return None

def deleteExpiredGames():
    """
    # Delete all expired smelly SNP games
    # Plus random time so that its not always sending at the same time. Do it with flare!
    # Don't delete the FinalGamefortheYear as this is the last game of the year, Marc will have to delete this manually. Also the grand final game is techincally the final game but this needs to be manual atm
    :return:
    """

    if Utility.select().count() == 0:
        checkRanTime = Utility()
        rndNum = (randint(30, 210))
        checkRanTime.random_time = rndNum
        checkRanTime.save()
    else:
        for checkRanTime in Utility.select(Utility.random_time):
            rndNum = checkRanTime.random_time

    myMsg = Events.select().where(Events.FinalGamefortheYear == False)
    for x in myMsg:
        strStartTime = (datetime.datetime.strptime(str(x.date_expiry_time), "%Y-%m-%d %H:%M:%S")) - datetime.timedelta(hours=4) #Start time is 7pm but we're sending new invite after 3pm
        if strStartTime < (datetime.datetime.today() - datetime.timedelta(minutes=rndNum)):
            if DEBUG:
                logging.critical ("DELETEING THE GAME %s" % x.date_expiry_time)
            x.delete_instance(True)

            for raazfixplslater in Utility.select(Utility.random_time): #RAAZ to fix later but atm we only have 1 record stored so we can delete the whole table but later need to figure out how to just update the 1 record
                raazfixplslater.delete_instance()

            #for checkRanTime in Utility.select(Utility.random_time): #set new Random time
            #    rndNum = (randint(30, 210))
            #    checkRanTime.random_time = rndNum
            #    checkRanTime.save()

        elif strStartTime < (datetime.datetime.today() - datetime.timedelta(minutes=210)):     #Insurance policy; with more testing we can remove below
            if DEBUG:
                logging.critical ("Times up! Removing game %s" % x.date_expiry_time)
            x.delete_instance(True)

            for checkRanTime in Utility.select(Utility.random_time): #set new Random time
                rndNum = (randint(30, 210))
                checkRanTime.random_time = rndNum
                checkRanTime.save()


def autoAddGames():
    """
    #We will add games in automatically since they are scheduled every 3 weeks, use global defined field: Events_frequency
    :return:
    """

    if (Events.select().count() < Number_of_events_scheduled) and (Events.select().where(Events.FinalGamefortheYear == True).count() == 0):
       for eventz in Events.select().order_by(Events.date_expiry_time.desc()).limit(1):
           if DEBUG:
               logging.critical ("Got to less than 3 events: 1")

           strStartTime = datetime.datetime.strptime(str(eventz.date_expiry_time), "%Y-%m-%d %H:%M:%S")

           eventDate =  strStartTime + datetime.timedelta(weeks=Events_frequency)

           newHappening = Events()
           newHappening.date_expiry_time = eventDate

           try:
               newHappening.save()
               if DEBUG:
                   logging.critical ("Got to less than 3 events: 1a")

               format = "%d %b %Y"
               strEmailHeaderDate = eventDate.strftime(format)

               #strEndTime = eventDate + datetime.timedelta(hours=4)
               createCalendarEvent('SNP - ' + strEmailHeaderDate + ' Game', eventDate, (eventDate + datetime.timedelta(hours=4)))
               if DEBUG:
                   logging.critical ("Got to less than 3 events: 1b - " + strEmailHeaderDate)

           except IntegrityError:
               return

def newInvitesOut():
    """
    #Sent out Email blast for next SNP Game to all Players
    :return:
    """
    myMsg = ""
    format = "%d %b %Y"

    for listofEvents in Events.select().order_by(Events.date_expiry_time.asc()).limit(1):
        if listofEvents.sentFlag == False:
            if DEBUG:
                logging.critical ("newInvitesOut\n")
            listofEvents.sentFlag = True
            listofEvents.save()
            myMsg = myMsg + "SNP - %s - Invite" % listofEvents.date_expiry_time.strftime(format)

            for allPlayers in Player.select():
                SendMessage(service, 'me', CreateMessage (__SNP_From_Address__, allPlayers.email, myMsg, __SNP_Invite_Body__ + "\n\n" + __strUsageMsg__))
                if DEBUG:
                    logging.critical ("Send email for Player:  %s \n" % allPlayers.name)

            usageOne(Player.select(Player.id).where(Player.email == 'mnraaz@gmail.com')) #Add mnraaz automatically to all NEW games


def getReservationExpiry():
    """
    Using current time figure out what the expiry time should be;
     > 48 hours then 48 hours
     < 48 and > 24 then 24 hours
     < 24 and > 12 then 12 hours
     < 12 blast all ie set to today
    :return: A list with DateTime in 0 and string with the details of time remaining in 1
    """

    if DEBUG:
        logging.critical ("Got to getReservationExpiry")

    listExpiryTime = [datetime.datetime.today(), "0"]


    # Grab time from the next event
    for x in Events.select(Events.date_expiry_time).order_by(Events.date_expiry_time.asc()).limit(1):
        strExpiryTime = datetime.datetime.strptime(str(x.date_expiry_time), "%Y-%m-%d %H:%M:%S")
        logging.critical (strExpiryTime)
        delta = strExpiryTime - (datetime.datetime.today()) #- datetime.timedelta(days=1))

        if delta < datetime.timedelta(0, 0):
            logging.critical ("Opps! - Get out of here")
            listExpiryTime = [datetime.datetime.today(), "0"]
            return listExpiryTime

        if DEBUG:
            logging.critical (delta)
            logging.critical (delta.days)

        if delta.days != 0:
            if (delta.days >= 2):
                #return (datetime.datetime.today() + datetime.timedelta(days=2))
                listExpiryTime = [(datetime.datetime.today() + datetime.timedelta(days=2)), "two days"]

                if DEBUG:
                    logging.critical ("Two days delta")

                return listExpiryTime

            elif (delta.days >= 1) and (delta.days < 2):
                listExpiryTime = [(datetime.datetime.today() + datetime.timedelta(days=1)), "one day"]
                if DEBUG:
                    logging.critical ("One day delta")
                return listExpiryTime

        elif delta.days == 0:
            timedif = divmod(delta.total_seconds(), 60*60)
            time_in_hours =  (int((timedif[0])))

            if (time_in_hours <= 24) and (time_in_hours > 12):
                listExpiryTime = [(datetime.datetime.today() + datetime.timedelta(hours=12)), "12 hours"]
                if DEBUG:
                    logging.critical ("12 hours delta")
                return listExpiryTime
            elif (time_in_hours <= 12):
                listExpiryTime = [datetime.datetime.today(), "0 minutes (because it's game day!"]
                if DEBUG:
                    logging.critical ("0 delta")
                return listExpiryTime


    return listExpiryTime


def cleanup_on_Aisle_Reservation():
    # Check if we have expired Reservations
    for x in Reservations.select().where(~(Reservations.expiry_time >> None)):
        #logging.critical (x.expiry_time)
        strExpiryTime = datetime.datetime.strptime(str(x.expiry_time), "%Y-%m-%d %H:%M:%S.%f")
        if strExpiryTime < datetime.datetime.today():
            x.delete_instance(True)
            logging.critical ("Deleting Reservation %s" % x.expiry_time)

    #Check we have a spot open then check if the 1st one has been sent out; then email them
    if GuestList.select().count() < __MAX_Players_Invited__:
        for x in Reservations.select().order_by(Reservations.join_date.asc()).limit(1): #grab the oldest reservation
            #logging.critical ("Got to selecting 1st res" )
            if x.sentFlag == False:
                x.sentFlag = True
                resExpiryTime = getReservationExpiry()
                x.expiry_time = resExpiryTime[0]

                for y in Player.select(Player.id).where(Player.id == x.playerID):
                    myMsg2 = getSingleEmailfromSQLstring(y.id)
                    format = "%d %b %Y"

                    for listofEvents in Events.select().where(Events.id == getNextEventID()):
                        myMsg = "SNP - %s - Invite" % listofEvents.date_expiry_time.strftime(format)

                    SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, myMsg2, myMsg, __SNP_Reserve_Available_Email__ + "An email will be sent in " + resExpiryTime[1] + " to the next person in the reserve list if the spot is not filled.\n\n"
                                                                                                                                                                                     "So please hurry!"))

                    logging.critical ("Send Email with expiry time % s" % x.expiry_time)

                x.save()
                logging.critical ("Saved expiry %s" % x.expiry_time)

def main():

    global service
    global calendarService
    global driveService

    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)
    calendarService = discovery.build('calendar', 'v3', http=http)
    driveService = discovery.build('drive', 'v3', http=http)

    #clean_house()

    while True:
        create_tables()
        #return

        deleteExpiredGames()
        autoAddGames()
        newInvitesOut()
        cleanup_on_Aisle_Reservation()

        label_info = service.users().labels().get(userId='me', id='UNREAD').execute()
        #logging.critical (label_info['id'] + ' ' + str(label_info['messagesUnread']))

        # Figure out if there are any Unread emails in the inbox
        if (label_info['messagesUnread']) > 0:
            #logging.critical (label_info['id'])
            response = service.users().messages().list(userId='me', labelIds=label_info['id']).execute()
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = service.users().messages().list(userId='me', labelIds=label_info['id'], pageToken=page_token).execute()
                messages.extend(response['messages'])

            # Process each Un-read email
            for msg_id in reversed(messages):
                strEmail_addy = []
                strMylist = []

                message = service.users().messages().get(userId='me', id=msg_id['id']).execute()
                ModifyMessage(service, 'me', msg_id['id'], {"removeLabelIds":["UNREAD"]}) #Makes it Unread here!
                for header in message['payload']['headers']:
                    #logging.critical (header['name'])
                    if strip_string_to_lowercase(header['name']) == 'from':
                        #logging.critical (header['value'])
                        if header['value'].find("<") == -1:
                            strEmail_addy = [header['value'], '']
                            strMylist = ["", ""]
                        else:
                            strMylist = header['value'].split("<") #Name
                            strEmail_addy = strMylist[1].split(">") #Email address
                            #logging.critical (strMylist[0])

                    if strip_string_to_lowercase(header['name']) == 'subject':
                        strSubject = header['value']

                if DEBUG:
                    logging.critical (str(datetime.datetime.today()) + " : Email from: " + strEmail_addy[0] + " Subject is: " + strSubject)
                #checkExistingUser = -1
                checkExistingUser = Player.select().where(Player.email == strEmail_addy[0]).count()
                if checkExistingUser == 0:
                    #Only want a clean email with SNP in it, don't want stupid threads or replies or forwards. Clean email please!!!
                    if ((strSubject.lower()) == "snp") or ((str(GetMimeMessage1stLine(service, 'me',msg_id['id']))).lower() == "snp"):
                        new_user = Player(name=strMylist[0], email = strEmail_addy[0])
                        new_user.save() # new_user is now stored in the database
                        SendMessage(service, 'me', CreateMessage(__SNP_From_Address__, strEmail_addy[0], __SNP_Subject__, __SNP_WelcomeMsg__))
                        backupDB()

                else:
                    # Did strip as \r was coming in from email and messing up the .get in my dictionary also removed \r\n
                    # Nice read about why: http://programmers.stackexchange.com/questions/29075/difference-between-n-and-r-n
                    strSnippet = str(GetMimeMessage1stLine(service, 'me',msg_id['id']))
                    if DEBUG:
                        logging.critical ("Body is: " + strSnippet)
                    #logging.critical (" looks like: " + strSnippet)
                    #return
                    strUsageText = strSnippet.replace('  ', '').replace(' ,', ',').replace(', ', ',').replace(' ', ',').split(',')
                    usageOptions = {"1": usageOne,
                                    "2": usageTwo,
                                    "3": usageThree,
                                    "4": usageFour,
                                    "42": usageFortyTwo,
                                    "5": usageFive}
                    for charMsg in strUsageText:
                        func = usageOptions.get(charMsg, "null")
                        if DEBUG:
                            logging.critical ("charMsg is: " + charMsg)
                        if func != "null":
                            func(Player.select(Player.id).where(Player.email == strEmail_addy[0]))
                        else: #The following are Admin ONLY actions. Special Email addresses are required to process these requests
                            if charMsg == "100":
                                usage100(strSubject, strEmail_addy[0])
                            elif charMsg == "101":
                                usage101(strSubject,strEmail_addy[0])
                            elif charMsg == "102":
                                usage102(strSubject,strEmail_addy[0])
                            else:
                                if (strSubject.find('Tentative: SNP -') == -1) and ((strSubject.find('Declined: SNP -')) == -1) and ((strSubject.find('Accepted: SNP -')) == -1) and ((strSubject.find('Accepted: Updated Invitation: SNP -')) == -1) and ((strSubject.find('Accepted: Invitation: SNP -')) == -1) and ((strSubject.find('Declined: Invitation: SNP - ')) == -1) and ((strSubject.find('Tentative: Invitation: SNP - ')) == -1):
                                    SendMessage(service, 'me', CreateMessage (__SNP_From_Address__, strEmail_addy[0], __SNP_Subject__, __strUsageMsg__))
                                    if DEBUG:
                                        logging.critical ("Sent What da email??")

                                break #VERY important otherwise will SPAM for every space in the email and every unread invalid email....not happy Jan!



        #logging.critical ("Out bro!")
        #sqlite_db.close()
        #logging.critical ("Sleeping")
        sleep(5) # delays for 5 seconds
        #logging.critical ("Awake")

if __name__ == '__main__':
    main()
    sys.exit()
