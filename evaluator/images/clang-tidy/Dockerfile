FROM alpine:edge
RUN apk update && apk add clang-extra-tools libc-dev linux-headers python3 py3-yaml libstdc++ g++
ADD analyze.py urls.json /
CMD /analyze.py
