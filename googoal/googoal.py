import os
import httplib2
import json

from .config import *

if "google" in config:
    if "oauth2_keyfile" in config["google"]:  # Check if config file is set up
        keyfile = os.path.expanduser(
            os.path.expandvars(config["google"]["oauth2_keyfile"])
        )
    else:
        keyfile = None
else:
    keyfile = None

NEW_OAUTH2CLIENT = False
try:
    # See this change: https://github.com/google/oauth2client/issues/401
    from oauth2client.service_account import ServiceAccountCredentials

    NEW_OAUTH2CLIENT = True
except ImportError:
    try:
        from oauth2client.client import SignedJwtAssertionCredentials
    except ImportError:
        api_available = False


class Google_service:
    """Base class for accessing a google service"""

    # Get a google API connection.
    def __init__(self, scope=None, credentials=None, http=None, service=None):
        if service is None:
            if http is None:
                if credentials is None:
                    if keyfile is not None:
                        if os.path.exists(keyfile):
                            with open(keyfile) as file:
                                self._oauthkey = json.load(file)
                            self.email = self._oauthkey["client_email"]
                            self.key = bytes(self._oauthkey["private_key"], "UTF-8")
                            self.scope = scope

                            if NEW_OAUTH2CLIENT:
                                self.credentials = ServiceAccountCredentials.from_json_keyfile_name(
                                    os.path.join(keyfile), self.scope
                                )
                                # self.credentials = ServiceAccountCredentials.from_p12_keyfile(self.email, self.keyos.path.join(keyfile), self.scope)
                            else:
                                self.credentials = SignedJwtAssertionCredentials(
                                    self.email, self.key, self.scope
                                )
                        else:
                            raise FileNotFoundError("keyfile " + file + " not found, update its location in _googoal.yml")
                    else:
                        raise Exception("No keyfile entry provided in config file for OAuth 2.0 access, see https://developers.google.com/identity/protocols/oauth2 to find out how to generate the file and place entry in _googoal.yml")
                else:
                    self.credentials = credentials
                    self.key = None
                    self.email = None

                http = httplib2.Http()
                self.http = self.credentials.authorize(http)
            else:
                self.http = http
        else:
            self.service = service

