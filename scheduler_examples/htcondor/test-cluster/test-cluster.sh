#!/bin/sh
hostname
lscpu
cat /proc/cpuinfo
free -h
printenv
vmstat
uname -a
lsb_release -a
taskset -cp $$
