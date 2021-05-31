googoal
===

<p align="left">
  <a href="https://github.com/lawrennd/googoal"><img alt="GitHub Actions status" src="https://github.com/lawrennd/googoal/workflows/code-tests/badge.svg"></a>
</p>

Software for interfacing with Google Services. This code was originally incorporated with the `pods` software, but split out in May 2021.


To access a spreadsheet from the script, you need to follow the
protocol for Oauth 2.0, the process is described [here](https://developers.google.com/identity/protocols/OAuth2).

Once you have the key file, you can specify its location in the
`_googoal.yml` file, using for example

```
# Set the email address of an account to access google doc information.
oauth2_keyfile: $HOME/oauth2-key-file-name.json
```
