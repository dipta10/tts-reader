#!/bin/bash

file_name=$1
playback_speed=$2
volume_level=$3

# atempo=1.7 -> sets playback speed
# volume=.5 -> sets volume level
ffplay -hide_banner -loglevel panic \
  -nostats -autoexit -nodisp  -af "atempo=${playback_speed},volume=${volume_level}" \
  /tmp/$file_name
