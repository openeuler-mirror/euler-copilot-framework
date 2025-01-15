#!/bin/bash


docker rm -f frame
docker build -t euler-copilot-frame .
#docker run -d --restart=always --network host --name frame -e TZ=Asia/Shanghai euler-copilot-frame
