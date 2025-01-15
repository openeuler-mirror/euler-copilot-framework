node {
    properties([
        parameters([
            string(name: "REPO", defaultValue: "framework-dev", description: "当前项目名")
        ])
    ])
    
    echo "拉取代码仓库"
    checkout scm
    
    def BUILD = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
    def reg = ""
    
    withCredentials([string(credentialsId: "reg_host", variable: "REG_HOST")]) {
        reg = "${REG_HOST}"
    }
    echo "构建当前分支Docker Image镜像"
    docker.withRegistry("https://${reg}", "dockerAuth") {
        def image = docker.build("${reg}/${params.REPO}:${BUILD}", "-f ./Dockerfile .")
        image.push()
    }

    def remote = [:]
    remote.name = "machine"
    withCredentials([string(credentialsId: "ssh_host", variable: "HOST")]) {
        remote.host = "${HOST}"
    }
    withCredentials([usernamePassword(credentialsId: "ssh", usernameVariable: 'sshUser', passwordVariable: 'sshPass')]) {
        remote.user = sshUser
        remote.password = sshPass
    }
    remote.allowAnyHosts = true
        
    echo "清除构建缓存"
    sshCommand remote: remote, command: "sh -c \"docker rmi ${reg}/${params.REPO}:${BUILD} || true\";"
    sshCommand remote: remote, command: "sh -c \"docker image prune -f || true\";";
    sshCommand remote: remote, command: "sh -c \"docker builder prune -f || true\";";
            
    echo "重新部署"
    sshCommand remote: remote, command: "sh -c \"kubectl -n euler-copilot set image deployment/framework-deploy framework=${reg}/${params.REPO}:${BUILD}\";"
}