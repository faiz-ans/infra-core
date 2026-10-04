#!/bin/sh
set -eu
sed "s/__NAS_LAN_IP__/${NAS_LAN_IP}/g" /etc/prometheus/prometheus.yml.template \
  > /etc/prometheus/prometheus.yml
