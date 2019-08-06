#! /usr/bin/env python
"""
Pro Arc fetch and push service
"""
import os
import logging
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
URL = os.environ.get('url', '')
AUTH = os.environ.get('authentication', "")

FILE_URL_KEY = os.environ.get('file_url')
FILE_NAME_KEY = os.environ.get('file_name')


def get_soap_client():
    """
    function to build and return SOAP client
    :return: zeep soap client object
    """
    if AUTH.lower() == "basic":
        username = os.environ.get('username')
        password = os.environ.get('password')
        LOG.info("Using authentication")
        session = Session()
        session.auth = HTTPBasicAuth(username, password)
        transport = Transport(session=session, timeout=TIMEOUT)
    else:
        LOG.info("Skipping authentication")
        transport = Transport(timeout=TIMEOUT)

    return Client(URL, transport=transport)


SOAP_CLIENT = get_soap_client()


@APP.route('/toproarc/<path:path>', methods=['POST'])
def toproarc(path):
    """
    Funciton to dosnload file based on data from provided entity and store it in ProArc
    :param path: SOAP method to call see https://proarctest-akersolutions.msappproxy.net/
    FileManager section
    :return: 200 Response if everything is ok
    """
    if path is None:
        return Response("Missing path/method to WS", status=400, mimetype='text/plain')

    entity = request.get_json()

    if isinstance(entity, list):
        return Response("Multiple entities is not supported", status=400, mimetype='text/plain')

    download_file(entity[os.environ.get('file_url')], entity[os.environ.get('file_name')])

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

    entity = {
        "_soapheaders": {},
        "files": {
            "ListItems": {
                "DownloadFile": {
                    "FileRno": file_id
                }
            }
        },
        "id": os.environ.get('proarc_user')
    }

    # Continuing on the soap call
    if os.environ.get('transit_decode', 'false').lower() == "true":
        LOG.info("transit_decode is set to True.")
        entity = typetransformer.transit_decode(entity)

    LOG.info(f"Finished creating request: {str(entity)}")

    response = do_soap(entity, SOAP_CLIENT, path)
    LOG.info(f"SOAPResponse : \n{str(response)}\n----End-Response----")
    try:
        file_stream = read_file(filename)
    except IOError as exc:
        exc_message = f" Could not open {filename}: {exc}"
        LOG.info(exc_message)
        return Response(response=exc_message, status=404)

    return Response(response=file_stream, status=200)


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
