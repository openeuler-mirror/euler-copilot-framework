#!/bin/bash
function check_pip {
    echo -e "[Info]检查pip3";
    if ! [[ -x "$(command -v pip3)" ]]; then
        echo -e "\033[31m[Error]未找到pip3，将进行安装\033[0m";
        yum install -y python3 python3-pip;
        if [[ $? -ne 0 ]]; then
            echo -e "[Error]安装python3和pip失败";
            return 1;
        fi
        echo -e "\033[32m[Success]python3与pip安装成功\033[0m";
    fi
    echo -e "\033[32m[Success]python3与pip已存在\033[0m";
    return 0;
}

function check_huggingface {
    echo -e "[Info]下载与安装最新huggingface_hub库";
    pip3 install -U huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple;
    if [[ $? -ne 0 ]]; then
        echo -e "\033[31m[Error]huggingface_hub安装失败\033[0m";
        return 1;
    fi
    echo -e "\033[32m[Success]huggingface_hub安装成功\033[0m";

    curl https://hf-mirror.com --connect-timeout 5 -s > /dev/null;
    if [[ $? -ne 0 ]]; then
        echo -e "\033[31m[Error]HuggingFace镜像站无法连接，无法自动下载模型\033[0m";
        return 1;
    fi
    return 0;
}

function download_small_model {
    RERANKER="BAAI/bge-reranker-large";
    EMBEDDING="bge-mixed-model.tar.gz";

    export HF_ENDPOINT=https://hf-mirror.com;
    # 下载reranker
    huggingface-cli download --resume-download $RERANKER --local-dir $(echo $RERANKER | cut -d "/" -f 2);
    if [[ $? -ne 0 ]]; then
        echo -e "[Error]下载模型权重失败：$RERANKER \033[0m";
        return 1;
    fi
    # 解压embedding
    tar -xzf $EMBEDDING;
    if [[ $? -ne 0 ]]; then
        echo -e "[Error]解压模型权重失败：$EMBEDDING \033[0m";
        return 1;
    fi
    rm -f $EMBEDDING;
    echo -e "\033[32m[Success]Reranker与Embedding模型配置成功\033[0m";
    return 0;
}


function main {
    check_pip
    if [[ $? -ne 0 ]]; then
        return 1;
    fi

    check_huggingface
    if [[ $? -ne 0 ]]; then
        return 1;
    fi

    download_small_model
    if [[ $? -ne 0 ]]; then
        return 1;
    fi
}

main