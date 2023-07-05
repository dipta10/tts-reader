#!/bin/bash

file_name=$1

ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.4" /home/dipta10/Desktop/temp/audio/$file_name
