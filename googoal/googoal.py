import os
import httplib2
import json

from .config import *

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


if "google" in config:
    if "oauth2_keyfile" in config["google"]:  # Check if config file is set up
        KEYFILE = os.path.expanduser(
            os.path.expandvars(config["google"]["oauth2_keyfile"])
        )
    else:
        KEYFILE = None
else:
    KEYFILE = None


class Google_service:
    """Base class for accessing a google service"""

    # Get a google API connection.
    def __init__(self, scope=None, credentials=None, http=None, service=None):
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if credentials is None:
            if os.path.exists("token.json"):
                self.credentials = Credentials.from_authorized_user_file("token.json", SCOPES)
            else:
                self.credentials = False
        else:
            self.credentials = credentials

        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                if KEYFILE is not None:
                    if os.path.exists(KEYFILE):
                        self.flow = InstalledAppFlow.from_client_secrets_file(
                            KEYFILE,
                            SCOPES
                        )
                        self.credentials = self.flow.run_local_server(port=0)
                        # Save credentials for next run
                        with open("token.json", "w") as token:
                            token.write(self.credentials.to_json())
                    else:
                        raise FileNotFoundError("keyfile " + KEYFILE + " not found, update its location in _googoal.yml")
                else:
                    raise Exception("No keyfile entry provided in config file for OAuth 2.0 access, see https://developers.google.com/identity/protocols/oauth2 to find out how to generate the file and place entry in _googoal.yml")
        if service is None:
            try:
                self.service = build("drive", "v3", credentials=self.credentials)
            except HttpError as error:
                raise Exception(f"Cannot access service: {error}")
        else:
            self.service = service
            
        if http is None:
            http = httplib2.Http()
            self.http = self.credentials.authorize(http)
        else:
            self.http = http

