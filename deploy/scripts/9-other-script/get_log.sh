#!/bin/bash
function help {
        echo -e "Usage: ./get_log.sh [namespace] [log_time]";
        echo -e "Example: ./get_log.sh euler-copilot 1h";
}

function main {
        echo -e "[Info] Starting to collect pod logs";
        time=$(date -u +"%s");
        echo -e "[Info] Current namespace: $1, Current timestamp: $time"
        filename="logs_$1_$time";

        mkdir $filename;
        echo $time > $filename/timestamp;

        echo "[Info] Starting log collection";
        kubectl -n $1 events > $filename/events.log;

        pod_names=$(kubectl -n $1 get pods -o name);
        while IFS= read -r line || [[ -n $line ]]; do
                mkdir -p $filename/$line;
                kubectl -n $1 describe $line > $filename/$line/details.log;
                kubectl -n $1 logs --previous --since $2 --all-containers=true --ignore-errors=true $line > $filename/$line/previous.log;
                kubectl -n $1 logs --since $2 --all-containers=true --ignore-errors=true $line > $filename/$line/current.log;
        done < <(printf '%s' "$pod_names");

        tar -czf $filename.tar.gz $filename/;
        rm -rf $filename;

        echo -e "[Info] Log collection completed, please provide $filename.tar.gz to us for analysis";
}

if [[ $# -lt 2 ]]; then
        help
else
        main $1 $2;
fi
