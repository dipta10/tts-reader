#!/bin/bash


output_text=$1
selected_text=$2

echo "selected text:"
echo $selected_text

cd ./lib/piper
echo "cur dir"
pwd
echo "$selected_text" > from-i3.txt

echo "$selected_text" | \
  ./piper --model en_US-amy-medium.onnx --output_file /tmp/$output_text



# echo "$selected_text" | \
#   ./piper --model en-us-ryan-high.onnx --output_file ~/Desktop/welcome.wav

# echo "$selected_text" | \
#   ./piper --model en-us-ryan-medium.onnx --output_file ~/Desktop/welcome.wav

# using ryan the following does not work!! :v
# Another important thing to note is our use of the extended option when calling bodyParser.urlencoded.

#ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.4" ~/Desktop/welcome.wav

# -nodisp = no display
