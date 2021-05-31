import os
import httplib2
import json

from .config import *

from googleapiclient import errors
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest

from .googoal import Google_service

class Drive(Google_service):
    """
    Class for accessing a google drive and managing files.
    """

    def __init__(self, scope=None, credentials=None, http=None, service=None):
        if scope is None:
            scope = ["https://www.googleapis.com/auth/drive"]
        Google_service.__init__(
            self, scope=scope, credentials=credentials, http=http, service=service
        )
        if service is None:
            self.service = build("drive", "v2", http=self.http)

    def ls(self):
        """List all resources on the google drive"""
        results = []
        page_token = None
        while True:
            param = {}
            if page_token:
                param["pageToken"] = page_token
            files = self.service.files().list(**param).execute()
            results.extend(files["items"])
            page_token = files.get("nexPageToken")
            if not page_token:
                break
        files = []
        for result in results:
            if not result["labels"]["trashed"]:
                files.append(
                    Resource(
                        id=result["id"],
                        name=result["title"],
                        mime_type=result["mimeType"],
                        url=result["alternateLink"],
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

    def __init__(self, name=None, mime_type=None, url=None, id=None, drive=None):

        if drive is None:
            self.drive = Drive()
        else:
            self.drive = drive

        if id is None:
            if name is None:
                name = "Google Drive Resource"
            # create a new sheet
            body = {"mimeType": mime_type, "title": name}
            try:
                self.drive.service.files().insert(body=body).execute(
                    http=self.drive.http
                )
            except (errors.HttpError):
                print("Http error")

            self._id = (
                self.drive.service.files()
                .list(q="title='" + name + "'")
                .execute(http=self.drive.http)["items"][0]["id"]
            )
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
            if url is None:
                self.get_url()
            else:
                self.url = url

    def delete(self, empty_bin=False):
        """Delete the file from drive."""
        if empty_bin:
            self.drive.service.files().delete(fileId=self._id).execute()
        else:
            self.drive.service.files().trash(fileId=self._id).execute()

    def undelete(self):
        """Recover file from the trash (if it's there)."""
        self.drive.service.files().untrash(fileId=self._id).execute()

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

        batch_request = BatchHttpRequest(callback=batch_callback)
        for count, user in enumerate(users):
            batch_entry = self.drive.service.permissions().insert(
                fileId=self._id,
                sendNotificationEmails=send_notifications,
                emailMessage=email_message,
                body={"value": user, "type": "user", "role": share_type},
            )
            batch_request.add(batch_entry, request_id="batch" + str(count))

        batch_request.execute()

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
        :param share_type: type of sharing for the given user, type options are 'reader', 'writer', 'owner'
        :type user: string
        :param send_notifications: 
        """
        if share_type not in ["writer", "reader", "owner"]:
            raise ValueError("Share type should be 'writer', 'reader' or 'owner'")

        permission_id = self._permission_id(user)
        permission = (
            self.drive.service.permissions()
            .get(fileId=self._id, permissionId=permission_id)
            .execute()
        )
        permission["role"] = share_type
        self.drive.service.permissions().update(
            fileId=self._id, permissionId=permission_id, body=permission
        ).execute()

    def _permission_id(self, user):

        return (
            self.drive.service.permissions()
            .getIdForEmail(email=user)
            .execute()["id"]
        )

    def share_list(self):
        """
        Provide a list of all users who can access the document in the form of 
        """
        permissions = (
            self.drive.service.permissions().list(fileId=self._id).execute()
        )

        entries = []
        for permission in permissions["items"]:
            entries.append((permission["emailAddress"], permission["role"]))
        return entries

    def revision_history(self):
        """
        Get the revision history of the document from Google Docs.
        """
        for item in (
            self.drive.service.revisions().list(fileId=self._id).execute()["items"]
        ):
            print(item["published"], item["selfLink"])

    def update_name(self, name):
        """Change the title of the file."""
        body = self.drive.service.files().get(fileId=self._id).execute()
        body["title"] = name
        body = (
            self.drive.service.files().update(fileId=self._id, body=body).execute()
        )
        self.name = name

    def get_mime_type(self):
        """Get the mime type of the file."""

        details = (
            self.drive.service.files()
            .list(q="title='" + self.name + "'")
            .execute(http=self.drive.http)["items"][0]
        )
        self.mime_type = details["mimeType"]
        return self.mime_type

    def get_name(self):
        """Get the title of the file."""
        self.name = (
            self.drive.service.files().get(fileId=self._id).execute()["title"]
        )
        return self.name

    def get_url(self):
        self.url = (
            self.drive.service.files()
            .get(fileId=self._id)
            .execute()["alternateLink"]
        )
        return self.url

    def update_drive(self, drive):
        """Update the file's drive API service."""
        self.drive = drive

    def _repr_html_(self):
        output = '<p><b>{title}</b> at <a href="{url}" target="_blank">this url.</a> ({mime_type})</p>'.format(
            url=self.url, title=self.name, mime_type=self.mime_type
        )
        return output

