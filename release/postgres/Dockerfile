FROM postgres:15-alpine@sha256:e18480a22d6e48f4d816a6696769b1ec09ac73a824c5649e49c7d8b684913f3d

# The official entrypoint supports starting directly as the owner of PGDATA.
# Этап F: уже выпущенные исправления дистрибутива ставятся при сборке.
RUN apk upgrade --no-cache && apk add --no-cache --upgrade 'libxml2>=2.13.9-r3' && rm /usr/local/bin/gosu
USER postgres
