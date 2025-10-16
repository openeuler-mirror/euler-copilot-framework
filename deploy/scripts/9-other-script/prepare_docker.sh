#!/bin/bash

function stop_docker {
        echo -e "[Info] Checking if Docker is installed";
        if ! [[ -x $(command -v docker) ]]; then
                echo -e "[Info] Docker not installed";
                return 0;
        fi

        echo -e "\033[33m[Warning] About to stop Docker service, confirm to continue?\033[0m";
        read -p "(Y/n): " choice;
    case $choice in
            [Yy])
                systemctl stop docker
                if [[ $? -ne 0 ]]; then
                    echo -e "\033[31m[Error] Failed to stop Docker service, aborting\033[0m"
                    return 1
                else
                    echo -e "\033[32m[Success] Docker service stopped successfully\033[0m"
                fi
                ;;
            [Nn])
                echo -e "\033[31m[Error] Operation cancelled\033[0m"
                return 1
                ;;
            *)
                echo -e "\033[31m[Error] Invalid input, operation cancelled\033[0m"
                return 1
                ;;
    esac

        echo -e "\033[33m[Warning] About to attempt to uninstall old Docker version, confirm to continue?\033[0m";
        read -p "(Y/n): " choice2;
    case $choice2 in
            [Yy])
                yum remove -y docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine
                if [[ $? -ne 0 ]]; then
                    echo -e "\033[31m[Error] Failed to uninstall old Docker version\033[0m"
                    return 1
                else
                    echo -e "\033[32m[Success] Old Docker version uninstalled\033[0m"
                fi
                ;;
            [Nn])
                echo -e "\033[31m[Error] Operation cancelled\033[0m"
                return 1
                ;;
             *)
                echo -e "\033[31m[Error] Invalid input, operation cancelled\033[0m"
                return 1
                ;;
    esac
        return 0;
}

function setup_docker_repo {
    echo -e "[Info] Setting up Docker RPM Repo";
    basearch=$(arch)
    cat > /etc/yum.repos.d/docker-ce.repo <<-EOF
[docker-ce-stable]
name=Docker CE Stable - \$basearch
baseurl=https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/centos/9/\$basearch/stable
enabled=1
gpgcheck=1
gpgkey=https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/centos/gpg
EOF
    echo -e "[Info] Updating yum package list";
    yum makecache
    if [[ $? -ne 0 ]]; then
        echo -e "\033[31m[Error] Failed to update yum package list\033[0m";
        return 1;
    else
        echo -e "\033[32m[Success] yum package list updated successfully\033[0m";
    fi
    return 0;
}

function install_docker {
        echo -e "[Info] Installing Docker";
        yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin;
        if [[ $? -ne 0 ]]; then
                echo -e "\033[31m[Error] Failed to install Docker\033[0m";
                return 1;
        else
                echo -e "\033[32m[Success] Docker installed successfully\033[0m";
        fi
        systemctl enable docker;

        echo -e "[Info] Setting up DockerHub mirror";
        if ! [[ -d "/etc/docker" ]]; then
                mkdir /etc/docker;
        fi

        if [[ -f "/etc/docker/daemon.json" ]]; then
                echo -e "\033[31m[Error] daemon.json already exists, please manually configure DockerHub mirror\033[0m";
        else
                cat > /etc/docker/daemon.json <<-EOF
{
        "registry-mirrors": [
                "https://docker.anyhub.us.kg",
                "https://docker.1panel.live",
                "https://dockerhub.icu",
                "https://docker.ckyl.me",
                "https://docker.awsl9527.cn",
                "https://dhub.kubesre.xyz",
            "https://gg3gwnry.mirror.aliyuncs.com"
        ]
}
EOF
        fi
        systemctl restart docker;
        if [[ $? -ne 0 ]]; then
                echo -e "\033[31m[Error] Docker startup failed\033[0m";
                return 1;
        else
                echo -e "\033[32m[Success] Docker started successfully\033[0m";
                return 0;
        fi
}

function login_docker {
        echo -e "[Info] Logging into Docker private registry";
        read -p "Registry URL: " url;
        read -p "Username: " username;
        read -p "Password: " password;

        docker login -u $username -p $password $url;
        if [[ $? -ne 0 ]]; then
                echo -e "\033[31m[Error] Docker login failed\033[0m";
                return 1;
        else
                echo -e "\033[32m[Success] Docker login successful\033[0m";
                return 0;
        fi
}

function main {
        echo -e "[Info] Updating Docker";

        stop_docker;
        if [[ $? -ne 0 ]]; then
                return 1;
        fi

        setup_docker_repo;
        if [[ $? -ne 0 ]]; then
                return 1;
        fi

        install_docker;
        if [[ $? -ne 0 ]]; then
                return 1;
        fi

        login_docker;
        if [[ $? -ne 0 ]]; then
                return 1;
        fi

        return 0;
}

main
