#!/bin/bash


output_text=$1
selected_text=$2

echo "selected text:"
echo $selected_text

cd ./lib/piper
echo "$selected_text" > from-i3.txt

echo "$selected_text" | \
  ./piper --model en_US-amy-medium.onnx --output_file /tmp/$output_text
