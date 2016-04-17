#!/bin/bash

yum update -y
yum install -y docker ecs-init nfs-utils
mount -o defaults,noatime %NFSHOST%:/mnt /mnt
usermod -a -G docker ec2-user
service docker start
start ecs
docker pull mjs472/wrf-base:0.0.1