# Smart Diagnosis Deployment Guide

## Preparation

+ Install [EulerCopilot Command Line (Smart Shell) Client](../../../quick_start/smart_shell/user_guide/shell.md) in advance

+ The machine to be diagnosed cannot install crictl and isula, only docker as the container management tool

+ Install gala-gopher and gala-anteater on the machine to be diagnosed

## Deploying gala-gopher

### 1. Prepare BTF File

**If the Linux kernel supports BTF, then there is no need to prepare a BTF file.** You can check whether the Linux kernel already supports BTF by the following command:

```bash
cat /boot/config-$(uname -r) | grep CONFIG_DEBUG_INFO_BTF
```

If the output result is `CONFIG_DEBUG_INFO_BTF=y`, then it means the kernel supports BTF. Otherwise it means the kernel does not support BTF.
If the kernel does not support BTF, you need to manually create a BTF file. The steps are as follows:

1. Obtain the vmlinux file of the current Linux kernel version

   The vmlinux file is stored in the `kernel-debuginfo` package, and the storage path is `/usr/lib/debug/lib/modules/$(uname -r)/vmlinux`.

   For example, for `kernel-debuginfo-5.10.0-136.65.0.145.oe2203sp1.aarch64`, the corresponding vmlinux path is `/usr/lib/debug/lib/modules/5.10.0-136.65.0.145.oe2203sp1.aarch64/vmlinux`.

2. Create BTF File

   Based on the obtained vmlinux file to create a BTF file. This step can be performed in your own environment. First, install the relevant dependency packages:

   ```bash
   # Note: the dwarves package contains the pahole command, and the llvm package contains the llvm-objcopy command
   yum install -y llvm dwarves
   ```

   Execute the following command line to generate the BTF file.

   ```bash
   kernel_version=4.19.90-2112.8.0.0131.oe1.aarch64  # Note: replace this with the target kernel version, which can be obtained by the uname -r command
   pahole -J vmlinux
   llvm-objcopy --only-section=.BTF --set-section-flags .BTF=alloc,readonly --strip-all vmlinux ${kernel_version}.btf
   strip -x ${kernel_version}.btf
   ```

   The generated BTF file name is in `<kernel_version>.btf` format, where `<kernel_version>` is the kernel version of the target machine, which can be obtained by the `uname -r` command.

### 2. Download gala-gopher Container Image

#### Online Download

The gala-gopher container image has been archived to the <https://hub.oepkgs.net/> repository, and can be obtained by the following command.

```bash
# Get the aarch64 architecture image
docker pull hub.oepkgs.net/a-ops/gala-gopher-profiling-aarch64:latest
# Get the x86_64 architecture image
docker pull hub.oepkgs.net/a-ops/gala-gopher-profiling-x86_64:latest
```

#### Offline Download

If you cannot download the container image through the online download method, contact me (He XiuJun 00465007) to obtain the compressed package.

After obtaining the compressed package, place it on the target machine, decompress it and load the container image, the command line is as follows:

```bash
tar -zxvf gala-gopher-profiling-aarch64.tar.gz
docker load < gala-gopher-profiling-aarch64.tar
```

### 3. Start gala-gopher Container

Container startup command:

```shell
docker run -d --name gala-gopher-profiling --privileged --pid=host --network=host -v /:/host -v /etc/localtime:/etc/localtime:ro -v /sys:/sys -v /usr/lib/debug:/usr/lib/debug -v /var/lib/docker:/var/lib/docker -v /tmp/$(uname -r).btf:/opt/gala-gopher/btf/$(uname -r).btf -e GOPHER_HOST_PATH=/host gala-gopher-profiling-aarch64:latest
```

Startup configuration parameter description:

+ `-v /tmp/$(uname -r).btf:/opt/gala-gopher/btf/$(uname -r).btf` : If the kernel supports BTF, then you can simply remove this configuration. If the kernel does not support BTF, you need to copy the previously prepared BTF file to the target machine and replace `/tmp/$(uname -r).btf` with the corresponding path.
+ `gala-gopher-profiling-aarch64-0426` : The tag corresponding to the gala-gopher container, replace with the actual downloaded tag.

Probe Startup:

+ `container_id` is the ID of the container to be observed
+ Start the sli and container probes separately

```bash
curl -X PUT http://localhost:9999/sli -d json='{"cmd":{"check_cmd":""},"snoopers":{"container_id":[""]},"params":{"report_period":5},"state":"running"}'
```

```bash
curl -X PUT http://localhost:9999/container -d json='{"cmd":{"check_cmd":""},"snoopers":{"container_id":[""]},"params":{"report_period":5},"state":"running"}'
```

探针关闭

```bash
curl -X PUT http://localhost:9999/sli -d json='{"state": "stopped"}'
```

```bash
curl -X PUT http://localhost:9999/container -d json='{"state": "stopped"}'
```

## Deploying gala-anteater

Source code deployment:

```bash
# Please specify the branch as 930eulercopilot
git clone https://gitee.com/GS-Stephen_Curry/gala-anteater.git
```

For installation and deployment, please refer to <https://gitee.com/openeuler/gala-anteater>
(please note that python version may cause setup.sh install to fail)

Image deployment:

```bash
docker pull hub.oepkgs.net/a-ops/gala-anteater:2.0.2
```

The `server` and `port` of Kafka and Prometheus in `/etc/gala-anteater/config/gala-anteater.yaml` need to be modified according to the actual deployment, and `model_topic`, `meta_topic`, `group_id` are customizable

```yaml
Kafka:
  server: "xxxx"
  port: "xxxx"
  model_topic: "xxxx" # customizable, keep consistent with rca configuration
  meta_topic: "xxxx" # customizable, keep consistent with rca configuration
  group_id: "xxxx" # customizable, keep consistent with rca configuration
  # auth_type: plaintext/sasl_plaintext, please set "" for no auth
  auth_type: ""
  username: ""
  password: ""

Prometheus:
  server: "xxxx"
  port: "xxxx"
  steps: "5"
```

The model training in gala-anteater depends on the data collected by gala-gopher, so please ensure that the gala-gopher probe runs normally for at least 24 hours before running gala-anteater.

## Deploying gala-ops

Introduction to each middleware:

kafka: A database middleware with distributed data分流 functionality, which can be configured as the current management node.

prometheus: Performance monitoring, configure the ip list of production nodes to be monitored.

Install kafka and prometheus directly through yum install, refer to the installation script <https://portrait.gitee.com/openeuler/gala-docs/blob/master/deploy/download_offline_res.sh#>

Only need to refer to the installation of kafka and prometheus in it

## Deploying euler-copilot-rca

Image pull

```bash
docker pull hub.oepkgs.net/a-ops/euler-copilot-rca:0.9.1
```

+ Modify the `config/config.json` file to configure gala-gopher image's `container_id` and `ip`, Kafka and Prometheus's `ip` and `port` (keep consistent with the above gala-anteater configuration)

```yaml
"gopher_container_id": "xxxx", # Container ID of gala-gopher
    "remote_host": "xxxx" # Machine IP address of gala-gopher
  },
  "kafka": {
    "server": "xxxx",
    "port": "xxxx",
    "storage_topic": "usad_intermediate_results",
    "anteater_result_topic": "xxxx",
    "rca_result_topic": "xxxx",
    "meta_topic": "xxxx"
  },
  "prometheus": {
    "server": "xxxx",
    "port": "xxxx",
    "steps": 5
  },
```
