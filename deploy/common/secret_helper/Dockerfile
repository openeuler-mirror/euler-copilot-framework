FROM hub.oepkgs.net/openeuler/openeuler:22.03-lts-sp4
RUN mkdir /app && \
    mkdir /secrets
WORKDIR /app
COPY . .
RUN sed -i 's|repo.openeuler.org|mirrors.nju.edu.cn/openeuler|g' /etc/yum.repos.d/openEuler.repo && \
    sed -i '/metalink/d' /etc/yum.repos.d/openEuler.repo && \
    sed -i '/metadata_expire/d' /etc/yum.repos.d/openEuler.repo && \
    yum update -y && \
    yum install python3 python3-pip -y && \
    yum clean all && \
    pip3 install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
ENV PYTHONPATH=/app
ENTRYPOINT ["python3", "./main.py"]