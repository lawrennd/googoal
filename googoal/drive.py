import os
import httplib2
import json

from .config import *
from .log import Logger


from googleapiclient import errors
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .googoal import Google_service

log = Logger(
    name=__name__,
    level=config["logging"]["level"],
    filename=config["logging"]["filename"]
)

class Drive(Google_service):
    """
    Class for accessing a google drive and managing files.
    """

    def __init__(self, scope=None, credentials=None, service=None):
        if scope is None:
            scope = ["https://www.googleapis.com/auth/drive.metadata"]
        Google_service.__init__(
            self, scope=scope, credentials=credentials, service=service
        )
        if service is None:
            self.service = build("drive", "v3", credentials=self.credentials)

    def ls(self):
        """List all resources on the google drive"""
        results = []
        page_token = None
        while True:
            param = {}
            if page_token:
                param["pageToken"] = page_token
            files = self.service.files().list(**param).execute()
            results.extend(files["files"])
            page_token = files.get("nexPageToken")
            if not page_token:
                break
        files = []
        for result in results:
            files.append(
                Resource(
                    id=result["id"],
                    name=result["name"],
                    mime_type=result["mimeType"],
                    drive=self,
                )
            )
        return files

    def _repr_html_(self):
        """Create a representation of the google drive for the notebook."""
        files = self.ls()
        output = "<p><b>Google Drive</b></p>"
        for file in files:
            output += file._repr_html_()

        return output

class Resource:
    """Resource found on the google drive.
    :param id: the google id of the spreadsheet to open (default is None which creates a new spreadsheet).
    """

    def __init__(self, name=None, mime_type=None, id=None, drive=None):

        if drive is None:
            self.drive = Drive()
        else:
            self.drive = drive

        if id is None:
            if name is None:
                name = "Google Drive Resource"
            # create a new sheet
            body = {"mimeType": mime_type, "name": name}
            log.info(f"Creating new file of type {mime_type} and name {name}")
            try:
                self.drive.service.files().create(body=body).execute()
            except HttpError as error:
                raise Exception(f"Cannot access service: {error}")

            try:
                self._id = (
                    self.drive.service.files()
                    .list(q="name='" + name + "'")
                    .execute()["files"][0]["id"]
                )
            except HttpError as error:
                raise Exception(f"Cannot access service: {error}")

            self.name = name
            self.mime_type = mime_type
        else:
            self._id = id
            if name is None:
                self.get_name()
            else:
                self.name = name
            if mime_type is None:
                self.get_mime_type()
            else:
                self.mime_type = mime_type
            self.get_url()

    def delete(self, empty_bin=False):
        """Delete the file from drive."""
        if empty_bin:
            self.drive.service.files().delete(fileId=self._id).execute()
        else:
            body = {"trashed": True}
            self.drive.service.files().update(fileId=self._id, body=body).execute()

    def undelete(self):
        """Recover file from the trash (if it's there)."""
        body = {"trashed": False}
        self.drive.service.files().update(fileId=self._id, body=body).execute()

    def share(
        self,
        users,
        share_type="writer",
        send_notifications=False,
        email_message=None,
    ):
        """
        Share a document with a given list of users.
        """
        if type(users) is str:
            users = [users]

        def batch_callback(request_id, response, exception):
            print("Response for request_id (%s):" % request_id)
            print(response)

            # Potentially log or re-raise exceptions
            if exception:
                raise exception

        for count, user in enumerate(users):
            self.drive.service.permissions().create(
                fileId=self._id,
                sendNotificationEmail=send_notifications,
                emailMessage=email_message,
                body={"emailAddress": user, "type": "user", "role": share_type},
            ).execute()

    def share_delete(self, user):
        """
        Remove sharing from a given user.
        """
        permission_id = self._permission_id(user)
        self.drive.service.permissions().delete(
            fileId=self._id, permissionId=permission_id
        ).execute()

    def share_modify(self, user, share_type="reader", send_notifications=False):
        """
        :param user: email of the user to update.
        :type user: string
        :param share_type: type of sharing for the given user, type options are 'reader', 'commenter', 'writer', 'owner'
        :type user: string
        :param send_notifications: 
        """
        if share_type not in ["writer", "commenter", "reader", "owner"]:
            raise ValueError("Share type should be 'writer', 'commenter', 'reader' or 'owner'")

        permission_id = self._permission_id(user)
        body = {"role": share_type}
        self.drive.service.permissions().update(
            fileId=self._id,
            permissionId=permission_id,
            body=body,
        ).execute()

    def _permission_id(self, user):
        """Return the id of a permission associated with a given user email"""
        permissions = self._get_permissions()
        for permission in permissions:
            if "emailAddress" in permission:
                if user == permission["emailAddress"]:
                    return permission["id"]
        raise ValueError(f"User {user} not found in permissions of sheet {self._id}")

    def _get_permissions(self):
        """Get the permissins information"""
        return self.drive.service.permissions().list(
            fileId=self._id,
            fields = "permissions"
        ).execute()["permissions"]
        
    def ispublished(self):
        """Is the resource published."""
        permissions = self._get_permissions()
        for permission in permissions:
            if permission["id"] == "anyoneWithLink":
                if permission["role"] in ["reader", "commenter", "writer"]:
                    return True
        return False
        
    def share_list(self):
        """
        Provide a list of all users who can access the document in the form of 
        """
        permissions = self._get_permissions()
        entries = []
        for permission in permissions:
            if "emailAddress" in permission:
                entries.append((permission["emailAddress"], permission["role"]))
            elif permission["id"] == "anyoneWithLink":
                entries.append(("Anyone with link", permission["role"]))
        return entries

    def revision_history(self):
        """
        Get the revision history of the document from Google Docs.
        """
        for item in (
            self.drive.service.revisions().list(fileId=self._id).execute()["files"]
        ):
            print(item["published"], item["selfLink"])

    def update_name(self, name):
        """Change the name of the file."""
        body= {"name": name}
        self.drive.service.files().update(
            fileId=self._id,
            body=body
        ).execute()
        self.name = name

    def get_mime_type(self):
        """Get the mime type of the file."""

        details = (
            self.drive.service.files()
            .list(q="name='" + self.name + "'")
            .execute()["files"][0]
        )
        self.mime_type = details["mimeType"]
        return self.mime_type

    def get_name(self):
        """Get the name of the file."""
        self.name = (
            self.drive.service.files().get(fileId=self._id, fields="name").execute()["name"]
        )
        return self.name

    def get_url(self):
        d = self.drive.service.files().get(fileId=self._id, fields="webViewLink").execute()
        self.url = d["webViewLink"]
        
        return self.url

    def update_drive(self, drive):
        """Update the file's drive API service."""
        self.drive = drive

    def _repr_html_(self):
        output = '<p><b>{name}</b> at <a href="{url}" target="_blank">this url.</a> ({mime_type})</p>'.format(
            url=self.url, name=self.name, mime_type=self.mime_type
        )
        return output

