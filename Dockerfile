FROM python:3.6.2

RUN apt-get update && apt-get install -y libxml2-dev libxslt1-dev supervisor

WORKDIR /home/dev/code

ADD . /home/dev/code
RUN pip3 install -r requirements.txt

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/home/dev/code/supervisord.conf"]
