FROM python:3.8-alpine

ENTRYPOINT ["/workdir/entrypoint.sh"]
WORKDIR /workdir
COPY requirements.txt .
RUN apk add --no-cache --virtual .pip-deps build-base && \
    pip3 install -r requirements.txt && \
    apk del .pip-deps
COPY . .

