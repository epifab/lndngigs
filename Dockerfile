FROM python:3.10.6

RUN mkdir /app
WORKDIR /app
ADD . /app
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["gunicorn", "lndngigs.web:app", "--bind", "0.0.0.0:8000"]
