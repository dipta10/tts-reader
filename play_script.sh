#!/bin/bash

echo "playing script...."
file_name=$1

ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.7" /tmp/$file_name
echo "done playing script...."
