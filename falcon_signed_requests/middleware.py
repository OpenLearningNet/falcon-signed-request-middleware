import hmac
import hashlib
import base64
import warnings
import falcon
from uuid import uuid1
from time import time
from time_uuid import TimeUUID
from io import BytesIO


class AuthenticRequestMiddleware(object):
    """Determines if a POST request is authentic, from a trusted source.

    When a request contains both the headers X-{header}-SIGNATURE and X-{header}-UUID 
    (where {header} denotes the configured header name) it signals that this request has 
    been sent from a trusted system (e.g. a trusted cloud service).

    If a request has a X-{header}-SIGNATURE header, then the request stream is consumed
    (as it is read for verification). If the request is deemed authentic, a request.body
    is provided with the body bytes, the request body is parsed using the media handler
    in order to provide request.media as well, and request.is_authentic is set to True, 

    The are headers generated by the requesting system by following the steps:
    1. generating a UUID1 for the request (which includes a timestamp)
    2. concatenating the UUID with the request body
    3. generating a HMAC (SHA256) base64-digest signature

    e.g. for the default configuration ::
        import base64
        import hashlib
        import hmac
        import uuid

        secret     = "<Shared Secret>".encode('utf-8')
        body       = "Body Bytes".encode('utf-8')
        request_id = str(uuid.uuid1()).encode("utf-8")

        signature  = base64.b64encode(
            hmac.new(
                key=secret,
                msg=request_id + body,
                digestmod=hashlib.sha256
            ).digest()
        )

    Only the trusted party bearing a shared secret (specified in config) can generate the 
    correct signature. These steps are then followed again (within this middleware) in order
    to generate another signature. If the two signatures match, the request is authentic.

    The UUID is used as both a timestamp (for timely expiry) and a nonce (to prevent replay).
    In combination with the provided signature, these request headers ensure that if the
    request is intercepted:
    * the request body and UUID cannot be modified (it is authentic)
    * there is a small time window in which the request can be used (it expires)
    * the request cannot be replayed (it is single-use)

    If these expiry and replay prevention features are not required, the "is_uuid_required" 
    option can be set to False. In this case when the UUID is not required, step 2. above is 
    also not performed. Additionally Redis is not required (for checking nonces) and can be 
    set to None in the __init__ argument.

    If a request is indeed authentic, "{header}-authenticated" is set to True in the request 
    context. Additionally, a "{header}-uuid" field is added if one is not provided in the header.
    If the request is not authentic, a falcon.HTTPForbidden is raised.

    The config dictionary expects the fields:
    * secret: the shared secret to use for generating signatures
    * header: the name of the header (see above, defaults to "auth")
    * expiry: the number of seconds a request is valid for (defaults to 300s, or 5min)
    * digest: the digest method to use ("base64" or "hex", defaults to "base64")
    * hash:   the hashing algorithm to use ("sha256" or "sha1", defaults to "sha256")
    * nonce_prefix: the prefix to use for nonce key names in redis (defaults to "nonce")
    * is_uuid_required: Whether the X-{header}-UUID is included in the check (defaults to True)

    redis_store is a Redis() connection object which is used to store nonces temporarily.
    """

    def __init__(self, config, redis_store=None):
        self.config = config
        self.redis = redis_store
        self.expiry = config.get("expiry", 300)  # 5 minute default
        self.digest = config.get("digest", "base64")
        self.hash = config.get("hash", "sha256")
        self.is_uuid_required = config.get("is_uuid_required", True)
        self.is_debug = config.get("debug_bypass", False)
        self.header_name = config.get("header", "auth")

    def _get_redis_key(self, request_id):
        return ".".join([self.config.get("nonce_prefix", "nonce"), request_id])

    def _has_unused_id(self, request_id):
        # Check the request id has not been previously used (as a nonce)
        assert self.redis is not None
        return self.redis.get(self._get_redis_key(request_id)) is None

    def _set_id_as_used(self, request_id):
        # Store a used request_id (as a nonce)
        # The nonce is expired twice the time after
        # the request to guard against minor timing
        # inconsistencies between systems
        assert self.redis is not None
        self.redis.set(self._get_redis_key(request_id), request_id, ex=self.expiry * 2)

    def _has_valid_request_id(self, request_id):
        # Extract the timestamp from the UUID1
        timestamp = TimeUUID(request_id).get_timestamp()

        # Check to see if this request has expired
        has_valid_timestamp = time() - timestamp < self.expiry

        # Check to see if this request has been attempted before
        # (prevent replay)
        is_unused = self._has_unused_id(request_id)

        # Both checks are required to pass in order to validate the request id
        return has_valid_timestamp and is_unused

    def _has_valid_signature(self, body, request_id, signature):
        if self.is_uuid_required:
            # Combine the request id and the (byte) contents of the request body
            # request_id is encoded to utf-8 as the payload is represented as bytes
            payload = request_id.encode("utf-8") + body
        else:
            # If no UUID is required, just the body is signed
            payload = body

        # Check that we have a valid secret
        secret = self.config.get("secret")
        if secret is None:
            raise ValueError("No secret configured")

        # Generate a SHA256 HMAC signature (base64 digest)
        # based off the configured shared secret
        hmac_fields = {
            "key": secret.encode("utf-8"),
            "msg": payload,
            "digestmod": hashlib.sha256 if self.hash == "sha256" else hashlib.sha1,
        }

        if self.digest == "base64":
            generated_signature = base64.b64encode(hmac.new(**hmac_fields).digest())
        else:
            generated_signature = hmac.new(**hmac_fields).hexdigest()

        # Constant-time comparison (to avoid timing attacks)
        # of the generated and the provided signatures
        # If these match, the request is authentic
        return hmac.compare_digest(generated_signature, signature)

    def process_resource(self, req, resp, resource, params):
        # retrieve the header info required
        signature = req.get_header("x-{}-signature".format(self.header_name))
        request_id = req.get_header("x-{}-uuid".format(self.header_name))

        if req.method != "POST" and signature is not None:
            return  # Only required to process POST requests

        # Request is not authenticated until proven so
        is_authenticated = False

        # A signature is present, there's a chance this is an authentic request
        # Read the body contents, as it needs to be authenticated
        body = req.bounded_stream.read()

        # Check to see if the request id and request body are authentic
        # (have not been tampered with, and the signature matches)
        has_matching_signature = self._has_valid_signature(body, request_id, signature)

        if has_matching_signature:
            if self.is_uuid_required:
                # Check to see if the request id has expired, or has been used before
                is_authenticated = self._has_valid_request_id(request_id)
            else:
                is_authenticated = True

        if is_authenticated and self.is_uuid_required:
            # This request has been authenticated
            # Record the request_id so that it cannot be authenticated again
            self._set_id_as_used(request_id)

        # Ensure every request has a uuid
        if request_id is None and self.is_uuid_required:
            request_id = str(uuid1())

        # Set context properties
        req.context["{}-uuid".format(self.header_name)] = request_id
        req.context["{}-authenticated".format(self.header_name)] = is_authenticated

        # Set request properties
        req.is_authentic = is_authenticated
        if is_authenticated:
            req.body = body

            # Parse any required media
            handler = req.options.media_handlers.find_by_media_type(
                req.content_type, req.options.default_media_type
            )

            try:
                req._media = handler.deserialize(
                    BytesIO(body), req.content_type, req.content_length
                )
            except Exception:
                pass
        else:
            raise falcon.HTTPForbidden(
                description="Access to this resource has been restricted"
            )

