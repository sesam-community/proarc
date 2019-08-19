# SOAP-sink built with Zeep

A small microservice to post data to a SOAP endpoint.
All entities must have a "_soapheaders" attribute.

[![Build Status](https://travis-ci.org/sesam-community/proarc.svg?branch=master)](https://travis-ci.org/sesam-community/proarc)

##### Environment options

* `PORT` - which port this service should run on
* `url` - URL to ProArc SOAP API
* `proarc_user` - Proarc user id to be used in SOAP requests
* `AUTH` - authentication schema to use
    * empty string - use without authenticaiton
    * basic - use basic authentication
* `username` - user name for basic authentication
* `password` - password for basic authentication
* `file_url` - input entity attribute that contains URL to file
that need to be uploaded to Proarc
* `file_name` - input entity attribute that contains name of file 
to be uploaded to Proarc
* `FILE_DOWNLOADER_URL` - URL to CIFS/SMB service (if used) that can download/(upload?)
files from CIFS share (Proarc stores files on such shares)
* `PROARC_SHARE_NAME` - Proarc share name 
* `PROARC_SHARE_PATH` - Proarc path to shared folder (relative to share name)

##### Example entity
```
{
  "_ts": 1486128503194780,
  "_previous": null,
  "_hash": "50d93095f6fb68e7517ea89e62c60af8",
  "_id": "29932",
  "_deleted": false,
  "_updated": 8,
  "_soapheaders": {
    "header": {
      [...]
    }
  },
  "Medarbeider": {
    [...]
  }
}
```
##### Example configuration:

```
{
  "_id": "proarc-service",
  "type": "system:microservice",
  "docker": {
    "environment": {
      "FILE_DOWNLOADER_URL": "http://proarc-file-loader-service:5000",
      "PROARC_SHARE_NAME": "ProArc",
      "PROARC_SHARE_PATH": "subfolder1/subfolder2/subfolder3",
      "authentication": "basic",
      "file_name": "file_name",
      "file_url": "file_url",
      "logLevelDefault": "DEBUG",
      "password": "$SECRET(password)",
      "proarc_user": "$ENV(username)",
      "transit_decode": "true",
      "url": "http://<proarc service URL>/FileManager.svc?wsdl",
      "username": "$ENV(username)"
    },
    "hosts": {
      "proarc.hostname.url": "<proarc IP address>"
    },
    "image": "sesamcommunity/proarc",
    "port": 5000
  },
  "verify_ssl": true
}

```