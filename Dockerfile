FROM python:3.7-alpine
RUN apk add --no-cache make
WORKDIR /app
COPY setup.cfg setup.py README.rst CHANGELOG.md ./
COPY stacker/ ./stacker
COPY scripts/ ./scripts
RUN python setup.py install
WORKDIR /project
ENTRYPOINT ["stacker"]
CMD ["--help"]
