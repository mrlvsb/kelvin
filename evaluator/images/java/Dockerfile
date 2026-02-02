FROM kelvin/base

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    openjdk-21-jdk \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://repo1.maven.org/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.tar.gz -P /tmp

RUN tar xf /tmp/apache-maven-*-bin.tar.gz -C /opt

RUN ln -s /opt/apache-maven-3.9.9/ /opt/maven

# To find out exactly folder path, run the docker image and enter
# `update-alternatives --config java` or `dirname $(dirname $(readlink -f $(which java)))` command
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk-amd64"
ENV M2_HOME="/opt/maven"
ENV MAVEN_HOME="/opt/maven"
ENV PATH="$M2_HOME/bin:$PATH"

RUN mkdir /.m2
RUN chmod u+rwx,g+rwx,o+rwx /.m2
