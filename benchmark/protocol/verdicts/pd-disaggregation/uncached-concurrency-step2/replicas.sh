#!/bin/bash
# Every 15 s: t_epoch, then for the prefill and decode Deployments spec/ready replicas and the
# HPA's current metric, desired and current replicas. Usage: replicas.sh OUT.csv NAMESPACE IDLABEL
OUT=$1; NS=$2; ID=$3
[ -s "$OUT" ] || echo "t_epoch,role,spec,ready,hpa_desired,hpa_current,hpa_current_metric,hpa_target_metric" > "$OUT"
while true; do
  t=$(date +%s)
  for r in prefill decode; do
    d=$(kubectl -n $NS get deploy $ID-$r -o jsonpath='{.spec.replicas},{.status.readyReplicas}' 2>/dev/null)
    h=$(kubectl -n $NS get hpa keda-hpa-$ID-$r -o jsonpath='{.status.desiredReplicas},{.status.currentReplicas},{.status.currentMetrics[0].external.current.averageValue},{.spec.metrics[0].external.target.averageValue}' 2>/dev/null)
    echo "$t,$r,$d,$h" >> "$OUT"
  done
  sleep 15
done
