FROM kelvin/base

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    openjdk-21-jdk \
    python3-pip \
    wget && \
    rm -rf /var/lib/apt/lists/*
RUN wget https://dlcdn.apache.org/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz -P /tmp
RUN tar xf /tmp/apache-maven-*-bin.tar.gz -C /opt
RUN ln -s /opt/apache-maven-3.9.9/ /opt/maven
RUN echo 'export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))\n\
export M2_HOME=/opt/maven\n\
export MAVEN_HOME=/opt/maven\n\
export PATH=$M2_HOME/bin:$PATH' > /etc/profile.d/maven.sh
RUN chmod +x /etc/profile.d/maven.sh
RUN /usr/bin/python3 -m pip install --break-system-packages bleach==5.0.1
RUN mkdir /.m2
RUN chmod u+rwx,g+rwx,o+rwx /.m2

ADD entry.py /
CMD /entry.py
