from __future__ import annotations

from flask import Flask, request

from services.reader import DefaultReaderController, ReaderController


def create_app(controller: ReaderController) -> Flask:
    app = Flask("tts-reader")

    @app.route("/read", methods=["GET", "POST"])
    def read():
        getaudio = request.args.get("getaudio", None) is not None
        if request.method == "POST":
            if not request.data:
                return "Failed to get the POSTed data"
            try:
                text = request.data.decode("utf-8")
            except UnicodeError:
                return "Failed to decode the POSTed data as UTF-8"
            return controller.read_text(text, getaudio)
        else:
            return controller.read_clipboard(getaudio)

    @app.get("/status")
    def status():
        return controller.status()

    @app.get("/toggle")
    def toggle():
        controller.toggle()
        return ""

    @app.get("/play")
    def play():
        controller.play()
        return ""

    @app.get("/pause")
    def pause():
        controller.pause()
        return ""

    @app.get("/reset")
    def reset():
        controller.reset()
        return ""

    @app.get("/skip")
    def skip():
        controller.skip()
        return ""

    @app.get("/volume/<float:value>")
    def volume(value: float):
        controller.set_volume(value)
        return ""

    @app.get("/speed/<float:value>")
    def speed(value: float):
        controller.set_speed(value)
        return ""

    return app

