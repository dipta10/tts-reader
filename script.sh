#!/bin/bash


selected_text=$1

echo "selected text:"
echo $selected_text

cd /home/dipta10/Desktop/packages/piper/piper
touch from-i3.txt
echo "$selected_text" > from-i3.txt

echo "$selected_text" | \
  ./piper --model en-us-amy-low.onnx --output_file ~/Desktop/welcome.wav

# echo "$selected_text" | \
#   ./piper --model en-us-ryan-high.onnx --output_file ~/Desktop/welcome.wav

# echo "$selected_text" | \
#   ./piper --model en-us-ryan-medium.onnx --output_file ~/Desktop/welcome.wav

# using ryan the following does not work!! :v
# Another important thing to note is our use of the extended option when calling bodyParser.urlencoded.

#ffplay -hide_banner -loglevel panic -nostats -autoexit -nodisp  -af "atempo=1.4" ~/Desktop/welcome.wav

# -nodisp = no display
