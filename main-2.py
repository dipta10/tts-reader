import asyncio
import tornado
from tornado.ioloop import IOLoop

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        print('hola!!!')

        self.write("Hello, world")

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
    ])

async def main():
    app = make_app()
    app.listen(8888)
    print(IOLoop.current())
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())