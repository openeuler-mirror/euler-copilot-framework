FROM hub.oepkgs.net/openeuler/openeuler:22.03-lts-sp4
RUN mkdir /app && \
    mkdir /secrets
WORKDIR /app
COPY . .
RUN yum update -y && \
    yum install python3 python3-pip -y && \
    yum clean all && \
    pip3 install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
ENV PYTHONPATH=/app
ENTRYPOINT ["python3", "./main.py"]