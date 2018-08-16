import uuid
import pytest
import json
import hashlib
from tests.conf import *


class TestDefaultMiddleware(ResourceFixture):
    @pytest.fixture(scope="function")
    def config(self):
        return {"secret": SECRET_KEY}

    def test_authentic(self, client, resource):
        request_id = uuid.uuid1()
        body, headers = get_authentic_request("Example Data", request_id=request_id)
        resp = client.simulate_request(
            method="POST", path="/test", headers=headers, body=body
        )
        assert resource.last_req.media == "Example Data"
        assert resp.status_code == 200
        assert resp.content == b"Authentic"

    def test_missing_id(self, client, resource):
        body, headers = get_authentic_request("Example Data", request_id=None)
        resp = client.simulate_request(
            method="POST", path="/test", headers=headers, body=body
        )
        assert resp.status_code == 403
        assert resp.content != b"Authentic"

    def test_get_passthrough(self, client):
        resp = client.simulate_request(method="GET", path="/test")
        assert resp.content == b"Success"

    def test_different_data(self, client, resource):
        request_id = uuid.uuid1()
        _, headers = get_authentic_request("Example Data", request_id=request_id)
        resp = client.simulate_request(
            method="POST", path="/test", headers=headers, body="Different Data"
        )
        assert resp.status_code == 403
        assert resp.content != b"Authentic"

    def test_inauthentic(self, client, resource):
        resp = client.simulate_request(
            method="POST", path="/test", body="Unauthenticated Data"
        )
        assert resp.status_code == 200
        assert resp.content == b"Inauthentic"


class TestGithubStyleMiddleware(ResourceFixture):
    @pytest.fixture(scope="function")
    def config(self):
        return {
            "secret": SECRET_KEY,
            "header": "hub",
            "signature_prefix": "sha1=",
            "hash": "sha1",
            "digest": "hex",
            "is_uuid_required": False,
        }

    def test_authentic(self, client, resource):
        body, headers = get_authentic_request(
            "Example Data",
            hash=hashlib.sha1,
            sig_prefix="sha1=",
            encoding="hex",
            header_name="Hub",
        )
        resp = client.simulate_request(
            method="POST", path="/test", headers=headers, body=body
        )
        assert resource.last_req.media == "Example Data"
        assert resp.status_code == 200
        assert resp.content == b"Authentic"

    def test_get_passthrough(self, client):
        resp = client.simulate_request(method="GET", path="/test")
        assert resp.content == b"Success"

    def test_different_data(self, client, resource):
        _, headers = get_authentic_request(
            "Example Data",
            hash=hashlib.sha1,
            sig_prefix="sha1=",
            encoding="hex",
            header_name="Hub",
        )
        resp = client.simulate_request(
            method="POST", path="/test", headers=headers, body="Different Data"
        )
        assert resp.status_code == 403
        assert resp.content != b"Authentic"

    def test_inauthentic(self, client, resource):
        resp = client.simulate_request(
            method="POST", path="/test", body="Unauthenticated Data"
        )
        assert resp.status_code == 200
        assert resp.content == b"Inauthentic"
