#!/bin/sh
set -e

A2X=${A2X-a2x}

if [ -z "$1" ]
then
	echo Usage: $0 '<input_dir> <output_dir>'
	exit 1
fi

echo Looking for a2x...
which "$A2X"
echo Ok.

echo Creating output directory...
mkdir -p "$2"
echo Ok.

# Block executable flag set by a2x
umask ugo-x

echo Creating manpages...
for src in "$1"/*.adoc
do
	echo $(basename "$src")
	"$A2X" -f manpage -D "$2" "$src"
done
echo Done.
