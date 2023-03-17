#!/bin/sh
if [ -z "${SLURM_PROCID}" ]
then
	echo Error: slurm task ID is empty. 1>&2
	exit 1
fi

date +"%F %H:%M:%S.%N Starting task ${SLURM_PROCID}..."

input=input/test-${SLURM_PROCID}.hdf5
output=output/output-${SLURM_PROCID}.hdf5
stdout=log/rail-estimate-test-${SLURM_PROCID}.out
stderr=log/rail-estimate-test-${SLURM_PROCID}.err

rail-estimate "$input" "$output" > "$stdout" 2> "$stderr"

date +"%F %H:%M:%S.%N Task ${SLURM_PROCID} finished."
