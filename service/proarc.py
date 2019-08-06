#! /usr/bin/env python
from logging import root

import requests
from flask import Flask, request, Response
from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from zeep import Client
from zeep.transports import Transport
import logger
import logging
import typetransformer
import os

rootlogger=logger.Logger()

app = Flask(__name__)
PORT = int(os.environ.get('PORT', '5000'))

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += os.environ.get('cipher', ':ECDHE-RSA-AES128-SHA')
timeout=int(os.environ.get('timeout', '30'))
url=os.environ.get('url')

auth = os.environ.get('authentication', "")
if auth.lower() == "basic":
    rootlogger.info("Using authentication")
    transport = Transport(http_auth=HTTPBasicAuth(os.environ.get('username'), os.environ.get('password')), timeout=timeout)
else:
    rootlogger.info("Skipping authentication")
    transport = Transport(timeout=timeout)

client = Client(url, transport=transport)


##Receiving soap-object
@app.route('/toproarc/<path:path>', methods=['POST'])
def toproarc(path):

    if path is None:
        return Response("Missing path/method to WS", status=500, mimetype='text/plain')

    entity = request.get_json()

    if isinstance(entity, list):
        return Response("Multiple entities is not supported",status=400, mimetype='text/plain')

    download_file(entity[os.environ.get('file_url')], entity[os.environ.get('file_name')])

    #removing entities here since they are not part of the soap call and will make the soap call fail
    del entity[os.environ.get('file_url')]
    del entity[os.environ.get('file_name')]

    #Continuing on the soap call
    if os.environ.get('transit_decode', 'false').lower() == "true":
        rootlogger.info("transit_decode is set to True.")
        entity = typetransformer.transit_decode(entity)

    rootlogger.info("Finished creating request: " + str(entity))

    response=do_soap(entity,client, path)
    rootlogger.info("SOAPResponse : \n" + str(response) + "\n----End-Response----")
    return Response("Thanks", mimetype='text/plain')


##Receiving soap-object
@app.route('/fromproarc/<path:path>', methods=['GET'])
def fromproarc(path):

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
        rootlogger.info("transit_decode is set to True.")
        entity = typetransformer.transit_decode(entity)

    rootlogger.info("Finished creating request: " + str(entity))

    response = do_soap(entity, client, path)
    rootlogger.info("SOAPResponse : \n" + str(response) + "\n----End-Response----")
    try:
        filestream = upload_file(filename)
    except Exception as e:
        rootlogger.info("  Could not open " + filename + " :%s"% e)
        return Response(response=("Could not open " + filename + " :%s"% e), status=404)

    return Response(response=filestream, status=200)


def download_file(url, local_filename):
    r = requests.get(url, stream=True)
    with open("/fileshare/"+local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
    return local_filename


def upload_file(filename):
    with open("/fileshare/"+filename, 'rb') as f:
        return f.read()


def do_soap(entity, client, path):

    headers = entity['_soapheaders']
    filtered_entity = {i:entity[i] for i in entity if not i.startswith('_') }
    filtered_entity['_soapheaders']=headers

    response = getattr(client.service, path)(**filtered_entity)
    return response


if __name__ == '__main__':
    if rootlogger.isEnabledFor(logging.DEBUG):
        app.run(debug=True, host='0.0.0.0', port=PORT)
    else:
        import cherrypy

        cherrypy.tree.graft(app, '/')
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
