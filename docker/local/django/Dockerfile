FROM docker.io/python:3.12.2-slim-bookworm AS python

# Stage 1 : Buld Wheels

FROM python AS python-build-stage

ARG BUILD_ENVIROMENT = local

RUN apt-get update

