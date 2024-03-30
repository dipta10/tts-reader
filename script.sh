#!/bin/bash

output_text=$1
selected_text=$2
model=$3
model_config=$4

echo "selected text:"
echo $selected_text

echo "$selected_text" | \
  piper --model "$model" --config "$model_config" --output-file /tmp/$output_text
