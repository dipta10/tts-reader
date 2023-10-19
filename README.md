# TTS Reader
Select text from anywhere and read aloud.

### Requirements
- ffmpeg
- xclip
- curl

### Steps to run
- Install requirements: `pip install -r requirements.txt`
- Run the application: `python3 main.py`
- Now select some text from your browser.
- Now run `curl --request GET --url http://localhost:5000/read`
- It should now read aloud the selected text.
- To stop reading aloud in the middle run `curl --request GET  --url http://localhost:5000/stop`

### Let's set a keybind
Now we can set a keybind to run the commands. For example if we're running i3wm we can add the following in our i3 config `~/.config/i3/config`.
```shell
set $alt Mod1
bindsym $alt+3 exec "curl --request GET --url http://localhost:5000/read"
bindsym $alt+shift+3 exec "curl --request GET  --url http://localhost:5000/stop"
```

### Disclaimer
This is my pet project. I switched from Windows to Ubuntu, mainly for i3wm and because my potato laptop works way faster here.
I was looking for an alternative for TTS reader where with a keybind I can make the app read the selected text aloud.

Since I didn't find a standalone application that can do it or perform as good as TTS Readers available on Windows, I decided to create one for myself using [Piper](https://github.com/rhasspy/piper) as a side project.

### Todo
- [ ] Use Piper python library and remove lib from repo