FROM python:3-alpine
MAINTAINER Ashkan Vahidishams "ashkan.vahidishams@sesam.io"
COPY ./service /service

RUN apk update
RUN apk add python-dev libxml2-dev libxslt-dev py-lxml musl-dev gcc

RUN pip install --upgrade pip

RUN pip install -r /service/requirements.txt

EXPOSE 5001/tcp

CMD ["python3", "-u", "./service/wsdl-microservice.py"]