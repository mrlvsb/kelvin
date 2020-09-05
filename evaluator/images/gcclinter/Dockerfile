FROM alpine:edge
RUN apk update && apk add gcc libc-dev python3
ADD analyze.py /
CMD /analyze.py
