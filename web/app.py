from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request, Query
from fastapi.responses import Response

from services.reader import ReaderController


def create_app(controller: ReaderController) -> FastAPI:
    app = FastAPI(title="tts-reader")

    @app.api_route("/read", methods=["GET", "POST"])
    async def read(request: Request, getaudio: Optional[str] = Query(None)):
        is_getaudio = getaudio is not None

        if request.method == "POST":
            body = await request.body()
            if not body:
                return "Failed to get the POSTed data"
            try:
                text = body.decode("utf-8")
            except UnicodeError:
                return "Failed to decode the POSTed data as UTF-8"
            result = controller.read_text(text, is_getaudio)
        else:
            result = controller.read_clipboard(is_getaudio)

        # If getaudio is True, controller returns bytes; otherwise returns str
        if is_getaudio and isinstance(result, bytes):
            return Response(content=result, media_type="audio/wav")
        return result

    @app.get("/status")
    async def status():
        return controller.status()

    @app.get("/toggle")
    async def toggle():
        controller.toggle()
        return ""

    @app.get("/play")
    async def play():
        controller.play()
        return ""

    @app.get("/pause")
    async def pause():
        controller.pause()
        return ""

    @app.get("/reset")
    async def reset():
        controller.reset()
        return ""

    @app.get("/skip")
    async def skip():
        controller.skip()
        return ""

    @app.get("/volume/{value}")
    async def volume(value: float):
        controller.set_volume(value)
        return ""

    @app.get("/speed/{value}")
    async def speed(value: float):
        controller.set_speed(value)
        return ""

    return app

