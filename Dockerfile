FROM hub.oepkgs.net/neocopilot/framework-baseimg:0.9.1

USER root
RUN sed -i 's/umask 002/umask 027/g' /etc/bashrc && \
    sed -i 's/umask 022/umask 027/g' /etc/bashrc && \
    yum remove -y gdb-gdbserver

USER eulercopilot
COPY --chown=1001:1001 --chmod=550 ./ /euler-copilot-frame/

WORKDIR /euler-copilot-frame
ENV PYTHONPATH /euler-copilot-frame
ENV TIKTOKEN_CACHE_DIR /euler-copilot-frame/assets/tiktoken

CMD bash -c "python3 -m gunicorn -c apps/gunicorn.conf.py apps.main:app"
