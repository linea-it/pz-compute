FROM debian:stable

ARG UID=1000
ARG GID=1000

RUN apt-get update -y && apt-get install -y vpnc ssh

# Update the package list, install sudo, create a non-root user, and grant password-less sudo permissions
RUN apt update && \
    apt install -y sudo && \
    addgroup --gid $GID nonroot && \
    adduser --uid $UID --gid $GID --disabled-password --gecos "" nonroot && \
    echo 'nonroot ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

USER nonroot
WORKDIR /home/nonroot

CMD [ "/bin/bash" ]
