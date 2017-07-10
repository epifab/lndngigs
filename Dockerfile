FROM python:3.5.2

RUN apt-get update && apt-get install libxml2-dev libxslt1-dev

WORKDIR /home/dev/code

ADD . /home/dev/code
RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "-m", "lndngigs.run"]
