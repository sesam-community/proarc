#! /usr/bin/env python
"""
Pro Arc fetch and push service
"""
import os
import logging
import uuid
from flask import Flask, request, Response
import urllib3
import requests
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client
from zeep.transports import Transport
import logger
import typetransformer

LOG = logger.logger()

APP = Flask(__name__)
PORT = int(os.environ.get('PORT', '5000'))

CIPHER_TO_ADD = os.environ.get('cipher', ':ECDHE-RSA-AES128-SHA')
urllib3.util.ssl_.DEFAULT_CIPHERS += CIPHER_TO_ADD

TIMEOUT = int(os.environ.get('timeout', '30'))
"""Proarc API URL"""
URL = os.environ.get('url', '')
"""
Available options:
- basic
- empty string (no authentication)
"""
AUTH = os.environ.get('authentication', "")

"""
input entity attribute that contains URL to file
that need to be uploaded to Proarc
"""
FILE_URL_KEY = os.environ.get('file_url')
"""
input entity attribute that contains name of file 
to be uploaded to proarc
"""
FILE_NAME_KEY = os.environ.get('file_name')
"""
URL to CIFS/SMB service that can download/(upload?)
files from CIFS share (Proarc stores files on such shares)
"""
FILE_DOWNLOADER_URL = os.environ.get('FILE_DOWNLOADER_URL')
"""
Proarc share name 
"""
PROARC_SHARE_NAME = os.environ.get('PROARC_SHARE_NAME')
"""
Proarc path to shared folder (relative to share name)
"""
PROARC_SHARE_PATH = os.environ.get('PROARC_SHARE_PATH')

LOG.debug(os.environ)


def get_soap_client():
    """
    function to build and return SOAP client
    :return: zeep soap client object
    """
    username = os.environ.get('username')
    password = os.environ.get('password')

    LOG.info(f"using {AUTH if AUTH else 'without'} authentication")

    if AUTH.lower() == "basic":
        session = Session()
        session.auth = HTTPBasicAuth(username, password)
        transport = Transport(session=session, timeout=TIMEOUT)
        return Client(URL, transport=transport)

    if AUTH.lower() == "wssecurity":
        from zeep.wsse.username import UsernameToken
        return Client(URL, wsse=UsernameToken(username, password), transport=Transport(timeout=TIMEOUT))

    transport = Transport(timeout=TIMEOUT)
    return Client(URL, transport=transport)


SOAP_CLIENT = get_soap_client()


@APP.route('/toproarc/<path:path>', methods=['POST'])
def toproarc(path):
    """
    Function to download file based on data from provided entity and store it in ProArc
    :param path: SOAP method to call see https://proarctest-akersolutions.msappproxy.net/
    FileManager section
    :return: 200 Response if everything is ok
    """
    if path is None:
        return Response("Missing path/method to WS", status=400, mimetype='text/plain')

    entity = request.get_json()

    if isinstance(entity, list):
        return Response("Multiple entities is not supported", status=400, mimetype='text/plain')

    download_file(entity[FILE_URL_KEY], entity[FILE_NAME_KEY])

    # removing entities here since they are not part of the soap call
    # and will make the soap call fail
    del entity[FILE_URL_KEY]
    del entity[FILE_NAME_KEY]

    # Continuing on the soap call
    if os.environ.get('transit_decode', 'false').lower() == "true":
        LOG.info("transit_decode is set to True.")
        entity = typetransformer.transit_decode(entity)

    LOG.info(f'Finished creating request: {str(entity)}')

    response = do_soap(entity, SOAP_CLIENT, path)
    LOG.info(f"SOAPResponse : \n{str(response)}\n----End-Response----")
    return Response("Thanks", mimetype='text/plain')


@APP.route('/fromproarc/<path:path>', methods=['GET'])
def fromproarc(path):
    """
    Function to receive a file from Pro Arc
    :param path:
    :return:
    """
    file_id = request.args.get('file_id')
    filename = request.args.get('filename')

    LOG.info(f'serving request for file_rno {file_id} and name {filename}')

    soap_entity = {
        "_soapheaders": {},
        "files": {
            "ListItems": {
                "DownloadFile": {
                    "FileRno": file_id
                }
            }
        },
        # It marked as optional in service definition but will follow to "Required session
        # object not set" error if omitted.
        "id": os.environ.get('proarc_user')
    }

    if os.environ.get('transit_decode', 'false').lower() == "true":
        LOG.debug("transit_decode is set to True.")
        soap_entity = typetransformer.transit_decode(soap_entity)

    LOG.debug(f"Finished creating request: {str(soap_entity)}")

    with SOAP_CLIENT.settings(raw_response=True):
        proarc_response = do_soap(soap_entity, SOAP_CLIENT, path)

    try:
        proarc_response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        res_text = proarc_response.text
        LOG.error(f'couldn\'t download {filename} cause {exc}: {res_text}')
        if 'Document does not exist or you do not have access' in res_text:
            return Response(response=res_text, status=200)
        raise exc

    LOG.debug(f"SOAPResponse : \n{str(proarc_response)}\n----End-Response----")

    local_file_name = None
    try:
        if FILE_DOWNLOADER_URL:
            LOG.debug(f"trying to download file {filename} from {FILE_DOWNLOADER_URL}")
            local_file_name = read_file_from_url(filename)
            file_stream = read_local_file(local_file_name)
        else:
            file_stream = read_file(filename)
    except IOError as exc:
        exc_message = f" Could not open {filename}: {exc}"
        LOG.error(exc_message)
        return Response(response=exc_message, status=500)
    finally:
        if local_file_name:
            os.remove(local_file_name)

    return Response(response=file_stream, status=200)


@APP.route('/<path:path>', methods=["GET"])
def make_request(path):
    """
    This function supports any "plain" requests to ProArc
    * GetFileInfo?fileRno=<file ref no>
    * GetFileInfosOnDocument?docRno=<doc ref no>
    * GetFileLog?fileRno=<filer ref no>
    :param path: ProArc endpoint
    :return:
    """
    entity = {i: request.args[i] for i in request.args}
    entity["_soapheaders"] = {}
    entity["id"] = os.environ.get('proarc_user')

    if os.environ.get('transit_decode', 'false').lower() == "true":
        LOG.info("transit_decode is set to True.")
        entity = typetransformer.transit_decode(entity)

    LOG.info(f"Prepared entity: {str(entity)}")

    response = do_soap(entity, SOAP_CLIENT, path)
    LOG.info(f"SOAPResponse : \n{str(response)}\n----End-Response----")
    return Response(status=200)


def download_file(url, local_filename):
    """
    Function to download file from provided URL and store it on local file share
    :param url: remote file location
    :param local_filename: name of stored file
    :return: local_filename
    """
    res = requests.get(url, stream=True)
    with open("/fileshare/" + local_filename, 'wb') as file:
        for chunk in res.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                file.write(chunk)
    return local_filename


def read_file(filename):
    """
    Function to read file with given name  from file share
    :param filename: name of file to be readed
    :return: file content
    """
    with open("/fileshare/" + filename, 'rb') as file:
        return file.read()


def read_local_file(filename):
    """
    Function to read file with given name  from file share
    :param filename: name of file to be readed
    :return: file content
    """
    with open(filename, 'rb') as file:
        return file.read()


def read_file_from_url(file_name):
    # NOTE the stream=True parameter below
    file_url = f'{FILE_DOWNLOADER_URL}/get/{PROARC_SHARE_NAME}/{PROARC_SHARE_PATH}/{file_name}'
    with requests.get(file_url, stream=True) as r:
        r.raise_for_status()
        # if we have to requests fetching the same file we need to be able to not mix them
        file_name += f"__{str(uuid.uuid4())}"
        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    # f.flush()
    return file_name


def do_soap(entity, client, path):
    """
    Function to perform SOAP call
    :param entity:
    :param client:
    :param path:
    :return:
    """
    headers = entity['_soapheaders']
    filtered_entity = {i: entity[i] for i in entity if not i.startswith('_')}
    filtered_entity['_soapheaders'] = headers

    response = getattr(client.service, path)(**filtered_entity)
    return response


if __name__ == '__main__':
    if LOG.isEnabledFor(logging.DEBUG):
        APP.run(debug=True, host='0.0.0.0', port=PORT)
    else:
        import cherrypy

        cherrypy.tree.graft(APP, '/')
        cherrypy.config.update({
            'environment': 'production',
            'engine.autoreload_on': True,
            'log.screen': False,
            'server.socket_port': PORT,
            'server.socket_host': '0.0.0.0',
            'server.thread_pool': 10,
            'server.max_request_body_size': 0
        })

        cherrypy.engine.start()
        cherrypy.engine.block()
