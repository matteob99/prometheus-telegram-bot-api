FROM python:3.8.6-alpine3.12 as base
RUN mkdir /code
WORKDIR /code

FROM base as builder
COPY requirements.txt /requirements.txt
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r /requirements.txt --no-warn-script-location

FROM base
COPY --from=builder /install /usr/local
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
COPY ./ /code/
RUN chmod 755 /code/entrypoint.sh
ENTRYPOINT ["/code/entrypoint.sh"]
