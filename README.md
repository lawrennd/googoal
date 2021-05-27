goggles
===

Software for interfacing with Google Services

## Google Docs Interface

The google docs interface requires

```
pip install httplib2
pip install oauth2client
pip install google-api-python-client
pip install gspread
pip install gdata
```

To access a spreadsheet from the script, you need to follow the
protocol for Oauth 2.0, the process is described (here)[https://developers.google.com/identity/protocols/OAuth2]

Once you have the key file, you can specify its location in the
`.ods_user.cfg` file, using for example

```
[google docs]
# Set the email address of an account to access google doc information.
oauth2_keyfile = $HOME/oauth2-key-file-name.json
```
