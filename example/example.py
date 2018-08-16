import falcon
from redis import Redis
from falcon_signed_requests import AuthenticRequestMiddleware
from wsgiref import simple_server

class ExampleResource(object):
    def on_post(self, req, resp):
        import json
        resp.status = falcon.HTTP_200

        if req.is_authentic:
            resp.body = (f"Request Authenticated: {json.dumps(req.media)}\n")
        else:
            resp.body = "Received an Unauthenticated request\n"

redis_store = Redis()

config = {
    "secret": "development"
}

app = falcon.API(middleware=[
    AuthenticRequestMiddleware(config, redis_store)
])

example = ExampleResource()

app.add_route("/example", example)

if __name__ == "__main__":
    httpd = simple_server.make_server("127.0.0.1", 8765, app)
    httpd.serve_forever()
