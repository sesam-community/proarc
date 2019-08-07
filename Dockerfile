FROM python:3-alpine
MAINTAINER Ashkan Vahidishams "ashkan.vahidishams@sesam.io"
COPY ./service /service

RUN apk update && apk add python-dev libxml2-dev libxslt-dev py-lxml musl-dev gcc && pip install --upgrade pip && \
pip install -r /service/requirements.txt && apk del gcc python-dev

EXPOSE 5000/tcp

CMD ["python3", "-u", "./service/proarc.py"]