FROM alpine:edge
RUN apk update && apk add clang-extra-tools libc-dev python3 py3-yaml
ADD analyze.py /
CMD /analyze.py
