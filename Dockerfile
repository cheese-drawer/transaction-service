FROM python:3.9.1-alpine3.12

# load source code
RUN mkdir /src
COPY src /src
COPY requirements/prod.txt /requirements.txt
# Enable easy dev on active container by using a bind mount via -v
# to give the container access to the source code on your machine
# For example, assuming you have a project directory structure like this:
# .
# |_ Dockerfile
# |_ README
# |_ .gitignore
# |_ app/
#   |_ .env/ ... python environment, local only
#   |_ .python-version
#   |_ requirements.txt
#   |_ .pylintrc
#   |_ src/
#     |_ server.py
#     |_ some_other_file.py
#       ... more application files here
#
# and you wanted to be able to develop the application files while
# running a container for dev purposes, you would bind the ./app
# directory in your project directory to the container's /app
# directory using `docker run -v ./app:/app ...` from your project root
VOLUME /src

# install python dependencies
RUN apk add --no-cache --virtual .build-deps \
    # needed to build psycopg2 & yarl
    gcc \
    # needed to build yarl
    musl-dev \
    # needed to build psycopg2
    postgresql-dev \
    # runtime dependency for psycopg2
    && apk add --no-cache libpq \
    # install python packages
    && pip install -r requirements.txt \
    # then remove build dependencies
    && apk del .build-deps

# start server
ENTRYPOINT ["python"]
CMD ["/src/server.py"]
