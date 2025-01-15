FROM hub.oepkgs.net/neocopilot/framework-baseimg:dev

USER root
RUN sed -i 's/umask 002/umask 027/g' /etc/bashrc && \
    sed -i 's/umask 022/umask 027/g' /etc/bashrc && \
    yum remove -y gdb-gdbserver

USER eulercopilot
COPY --chown=1001:1001 --chmod=550 ./ /euler-copilot-frame/

WORKDIR /euler-copilot-frame
ENV PYTHONPATH /euler-copilot-frame

CMD bash -c "python3 apps/main.py"
