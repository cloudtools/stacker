FROM python:2.7.10
MAINTAINER Mike Barrett

COPY scripts/docker-stacker /bin/docker-stacker
RUN mkdir -p /stacks && pip install --upgrade pip setuptools
WORKDIR /stacks
COPY . /tmp/stacker
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
RUN cd /tmp/stacker && python setup.py install && rm -rf /tmp/stacker

ENTRYPOINT ["docker-stacker"]
CMD ["-h"]
