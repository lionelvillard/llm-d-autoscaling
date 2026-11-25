#!/bin/bash
# Copy the poller pod's capture files into this directory (prefix pod-). Usage: pull.sh NAMESPACE CONTEXT
NS=$1; CTX=$2
for f in samples.csv pods.csv $(kubectl --context "$CTX" -n $NS exec poller -- bash -c 'cd /tmp; ls load-*.csv load-*.log' 2>/dev/null); do
  kubectl --context "$CTX" -n $NS exec poller -- cat /tmp/$f > pod-$f
done
