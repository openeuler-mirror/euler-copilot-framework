node {
    echo "拉取代码仓库"
    checkout scm
    
    def REPO = scm.getUserRemoteConfigs()[0].getUrl().tokenize('/').last().split("\\.")[0]
    def BRANCH = scm.branches[0].name.split("/")[1]
    def BUILD = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
    
    withCredentials([string(credentialsId: "host", variable: "HOST")]) {
        echo "构建当前分支Docker Image镜像"
        sh "sed -i 's|framework_base|${HOST}:30000/framework-baseimg|g' Dockerfile"
        docker.withRegistry("http://${HOST}:30000", "dockerAuth") {
            def image = docker.build("${HOST}:30000/${REPO}:${BUILD}", "-f Dockerfile .")
            image.push()
            image.push("${BRANCH}")
        }

        def remote = [:]
        remote.name = "machine"
        remote.host = "${HOST}"
        withCredentials([usernamePassword(credentialsId: "ssh", usernameVariable: 'sshUser', passwordVariable: 'sshPass')]) {
            remote.user = sshUser
            remote.password = sshPass
        }
        remote.allowAnyHosts = true
        
        echo "清除构建缓存"
        sshCommand remote: remote, command: "sh -c \"docker rmi ${HOST}:30000/${REPO}:${BUILD} || true\";"
        sshCommand remote: remote, command: "sh -c \"docker rmi ${REPO}:${BUILD} || true\";"
        sshCommand remote: remote, command: "sh -c \"docker rmi ${REPO}:${BRANCH} || true\";"
        sshCommand remote: remote, command: "sh -c \"docker image prune -f || true\";";
        sshCommand remote: remote, command: "sh -c \"docker builder prune -f || true\";";
        sshCommand remote: remote, command: "sh -c \"k3s crictl rmi --prune || true\";";
            
        echo "重新部署"
        withCredentials([usernamePassword(credentialsId: "dockerAuth", usernameVariable: 'dockerUser', passwordVariable: 'dockerPass')]) {
            sshCommand remote: remote, command: "sh -c \"cd /home/registry/registry-cli; python3 ./registry.py -l ${dockerUser}:${dockerPass} -r http://${HOST}:30000 --delete --keep-tags 'master' '0001' '330-feature' '430-feature' || true\";"
        }
        sshCommand remote: remote, command: "sh -c \"kubectl -n euler-copilot set image deployment/framework-deploy framework=${HOST}:30000/${REPO}:${BUILD}\";"
    }
}
