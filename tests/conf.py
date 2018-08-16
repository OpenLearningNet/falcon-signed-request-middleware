# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division

import base64
import hashlib
import hmac
import json
import requests

import os
import falcon
import pytest

from falcon import testing
from falcon_signed_requests import AuthenticRequestMiddleware

SECRET_KEY = "SecretKey1234"


def create_app(middleware, resource):

    api = falcon.API(middleware=[middleware])

    api.add_route("/test", resource)
    return api


class TestResource:
    def on_post(self, req, resp):
        if req.is_authentic:
            if json.loads(req.body) == req.media:
                resp.body = "Authentic"
            else:
                resp.body = "Fail"
        else:
            resp.body = "Inauthentic"

        self.last_req = req

    def on_get(self, req, resp):
        resp.body = "Success"


class ResourceFixture:
    @pytest.fixture(scope="function")
    def resource(self):
        return TestResource()


def get_authentic_request(
    data,
    request_id=None,
    hash=hashlib.sha256,
    encoding="base64",
    sig_prefix="",
    header_name="Auth",
):
    secret = SECRET_KEY.encode("utf-8")
    body = json.dumps(data).encode("utf-8")

    if request_id is not None:
        request_id = str(request_id)
        msg = request_id.encode("utf-8") + body
    else:
        msg = body

    hmac_sig = hmac.new(key=secret, msg=msg, digestmod=hash)

    if encoding == "base64":
        signature = base64.b64encode(hmac_sig.digest()).decode("utf-8")
    else:
        signature = hmac_sig.hexdigest()

    headers = {
        "Content-Type": "application/json",
        f"X-{header_name}-Signature": sig_prefix + signature,
    }

    if request_id is not None:
        headers.update({f"X-{header_name}-UUID": request_id})

    return (body, headers)


class FakeRedis:
    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def set(self, key, val, ex=None):
        self._data[key] = val


@pytest.fixture(scope="function")
def auth_req_middleware(config):
    return AuthenticRequestMiddleware(config, FakeRedis())


@pytest.fixture(scope="function")
def app(auth_req_middleware, resource):
    return create_app(auth_req_middleware, resource)


@pytest.fixture(scope="function")
def client(app):
    return testing.TestClient(app)
