"""Token Verifier module"""
import json
import time

import jwt
import requests

from auth0.exceptions import TokenValidationError


class SignatureVerifier:
    """Abstract class that will verify a given JSON web token's signature
    using the key fetched internally given its key id.

    Args:
        algorithm (str): The expected signing algorithm (e.g. RS256).
    """

    DISABLE_JWT_CHECKS = {
        "verify_signature": True,
        "verify_exp": False,
        "verify_nbf": False,
        "verify_iat": False,
        "verify_aud": False,
        "verify_iss": False,
        "require_exp": False,
        "require_iat": False,
        "require_nbf": False,
    }

    def __init__(self, algorithm):
        if not algorithm or type(algorithm) != str:
            raise ValueError("algorithm must be specified.")
        self._algorithm = algorithm

    def _fetch_key(self, key_id=None):
        """Obtains the key associated to the given key id.
        Must be implemented by subclasses.

        Args:
            key_id (str, optional): The id of the key to fetch.

        Returns:
            the key to use for verifying a cryptographic signature
        """
        raise NotImplementedError

    def _get_kid(self, token):
        """Gets the key id from the kid claim of the header of the token

        Args:
            token (str): The JWT to get the header from.

        Raises:
            TokenValidationError: if the token cannot be decoded, the algorithm is invalid
            or the token's signature doesn't match the calculated one.

        Returns:
            the key id or None
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError:
            raise TokenValidationError("token could not be decoded.")

        alg = header.get("alg", None)
        if alg != self._algorithm:
            raise TokenValidationError(
                'Signature algorithm of "{}" is not supported. Expected the token '
                'to be signed with "{}"'.format(alg, self._algorithm)
            )

        return header.get("kid", None)

    def _decode_jwt(self, token, secret_or_certificate):
        """Verifies and decodes the given JSON web token with the given public key or shared secret.

        Args:
            token (str): The JWT to get its signature verified.
            secret_or_certificate (str): The public key or shared secret.

        Raises:
            TokenValidationError: if the token cannot be decoded, the algorithm is invalid
            or the token's signature doesn't match the calculated one.
        """
        try:
            decoded = jwt.decode(
                jwt=token,
                key=secret_or_certificate,
                algorithms=[self._algorithm],
                options=self.DISABLE_JWT_CHECKS,
            )
        except jwt.exceptions.InvalidSignatureError:
            raise TokenValidationError("Invalid token signature.")
        return decoded

    def verify_signature(self, token):
        """Verifies the signature of the given JSON web token.

        Args:
            token (str): The JWT to get its signature verified.

        Raises:
            TokenValidationError: if the token cannot be decoded, the algorithm is invalid
            or the token's signature doesn't match the calculated one.
        """
        kid = self._get_kid(token)
        secret_or_certificate = self._fetch_key(key_id=kid)

        return self._decode_jwt(token, secret_or_certificate)


class SymmetricSignatureVerifier(SignatureVerifier):
    """Verifier for HMAC signatures, which rely on shared secrets.

    Args:
        shared_secret (str): The shared secret used to decode the token.
        algorithm (str, optional): The expected signing algorithm. Defaults to "HS256".
    """

    def __init__(self, shared_secret, algorithm="HS256"):
        super().__init__(algorithm)
        self._shared_secret = shared_secret

    def _fetch_key(self, key_id=None):
        return self._shared_secret


class AsymmetricSignatureVerifier(SignatureVerifier):
    """Verifier for RSA signatures, which rely on public key certificates.

    Args:
        jwks_url (str): The url where the JWK set is located.
        algorithm (str, optional): The expected signing algorithm. Defaults to "RS256".
    """

    def __init__(self, jwks_url, algorithm="RS256"):
        super().__init__(algorithm)
        self._fetcher = JwksFetcher(jwks_url)

    def _fetch_key(self, key_id=None):
        return self._fetcher.get_key(key_id)


class JwksFetcher:
    """Class that fetches and holds a JSON web key set.
    This class makes use of an in-memory cache. For it to work properly, define this instance once and re-use it.

    Args:
        jwks_url (str): The url where the JWK set is located.
        cache_ttl (str, optional): The lifetime of the JWK set cache in seconds. Defaults to 600 seconds.
    """

    CACHE_TTL = 600  # 10 min cache lifetime

    def __init__(self, jwks_url, cache_ttl=CACHE_TTL):
        self._jwks_url = jwks_url
        self._init_cache(cache_ttl)
        return

    def _init_cache(self, cache_ttl):
        self._cache_value = {}
        self._cache_date = 0
        self._cache_ttl = cache_ttl
        self._cache_is_fresh = False

    def _cache_expired(self):
        """Checks if the cache is expired

        Returns:
            True if it should use the cache.
        """
        return self._cache_date + self._cache_ttl < time.time()

    def _cache_jwks(self, jwks):
        """Cache the response of the JWKS request

        Args:
            jwks (dict): The JWKS
        """
        self._cache_value = self._parse_jwks(jwks)
        self._cache_is_fresh = True
        self._cache_date = time.time()

    def _fetch_jwks(self, force=False):
        """Attempts to obtain the JWK set from the cache, as long as it's still valid.
        When not, it will perform a network request to the jwks_url to obtain a fresh result
        and update the cache value with it.

        Args:
            force (bool, optional): whether to ignore the cache and force a network request or not. Defaults to False.
        """
        if force or self._cache_expired():
            self._cache_value = {}
            response = requests.get(self._jwks_url)
            if response.ok:
                jwks = response.json()
                self._cache_jwks(jwks)
            return self._cache_value

        self._cache_is_fresh = False
        return self._cache_value

    @staticmethod
    def _parse_jwks(jwks):
        """
        Converts a JWK string representation into a binary certificate in PEM format.
        """
        keys = {}

        for key in jwks["keys"]:
            # noinspection PyUnresolvedReferences
            # requirement already includes cryptography -> pyjwt[crypto]
            rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
            keys[key["kid"]] = rsa_key
        return keys

    def get_key(self, key_id):
        """Obtains the JWK associated with the given key id.

        Args:
            key_id (str): The id of the key to fetch.

        Returns:
            the JWK associated with the given key id.

        Raises:
            TokenValidationError: when a key with that id cannot be found
        """
        keys = self._fetch_jwks()

        if keys and key_id in keys:
            return keys[key_id]

        if not self._cache_is_fresh:
            keys = self._fetch_jwks(force=True)
            if keys and key_id in keys:
                return keys[key_id]
        raise TokenValidationError(f'RSA Public Key with ID "{key_id}" was not found.')


class TokenVerifier:
    """Class that verifies ID tokens following the steps defined in the OpenID Connect spec.
    An OpenID Connect ID token is not meant to be consumed until it's verified.

    Args:
        signature_verifier (SignatureVerifier): The instance that knows how to verify the signature.
        issuer (str): The expected issuer claim value.
        audience (str): The expected audience claim value.
        leeway (int, optional): The clock skew to accept when verifying date related claims in seconds.
        Defaults to 60 seconds.
    """

    def __init__(self, signature_verifier, issuer, audience, leeway=0):
        if not signature_verifier or not isinstance(
            signature_verifier, SignatureVerifier
        ):
            raise TypeError(
                "signature_verifier must be an instance of SignatureVerifier."
            )

        self.iss = issuer
        self.aud = audience
        self.leeway = leeway
        self._sv = signature_verifier
        self._clock = None  # visible for testing

    def verify(self, token, nonce=None, max_age=None, organization=None):
        """Attempts to verify the given ID token, following the steps defined in the OpenID Connect spec.

        Args:
            token (str): The JWT to verify.
            nonce (str, optional): The nonce value sent during authentication.
            max_age (int, optional): The max_age value sent during authentication.
            organization (str, optional): The expected organization ID (org_id) claim value. This should be specified
            when logging in to an organization.

        Returns:
            the decoded payload from the token

        Raises:
            TokenValidationError: when the token cannot be decoded, the token signing algorithm is not the expected one,
            the token signature is invalid or the token has a claim missing or with unexpected value.
        """

        # Verify token presence
        if not token or not isinstance(token, str):
            raise TokenValidationError("ID token is required but missing.")

        # Verify algorithm and signature
        payload = self._sv.verify_signature(token)

        # Verify claims
        self._verify_payload(payload, nonce, max_age, organization)

        return payload

    def _verify_payload(self, payload, nonce=None, max_age=None, organization=None):
        # Issuer
        if "iss" not in payload or not isinstance(payload["iss"], str):
            raise TokenValidationError(
                "Issuer (iss) claim must be a string present in the ID token"
            )
        if payload["iss"] != self.iss:
            raise TokenValidationError(
                'Issuer (iss) claim mismatch in the ID token; expected "{}", '
                'found "{}"'.format(self.iss, payload["iss"])
            )

        # Subject
        if "sub" not in payload or not isinstance(payload["sub"], str):
            raise TokenValidationError(
                "Subject (sub) claim must be a string present in the ID token"
            )

        # Audience
        if "aud" not in payload or not isinstance(payload["aud"], (str, list)):
            raise TokenValidationError(
                "Audience (aud) claim must be a string or array of strings present in"
                " the ID token"
            )

        if isinstance(payload["aud"], list) and self.aud not in payload["aud"]:
            payload_audiences = ", ".join(payload["aud"])
            raise TokenValidationError(
                'Audience (aud) claim mismatch in the ID token; expected "{}" but was '
                'not one of "{}"'.format(self.aud, payload_audiences)
            )
        elif isinstance(payload["aud"], str) and payload["aud"] != self.aud:
            raise TokenValidationError(
                'Audience (aud) claim mismatch in the ID token; expected "{}" '
                'but found "{}"'.format(self.aud, payload["aud"])
            )

        # --Time validation (epoch)--
        now = self._clock or time.time()
        leeway = self.leeway

        # Expires at
        if "exp" not in payload or not isinstance(payload["exp"], int):
            raise TokenValidationError(
                "Expiration Time (exp) claim must be a number present in the ID token"
            )

        exp_time = payload["exp"] + leeway
        if now > exp_time:
            raise TokenValidationError(
                "Expiration Time (exp) claim error in the ID token; current time ({})"
                " is after expiration time ({})".format(now, exp_time)
            )

        # Issued at
        if "iat" not in payload or not isinstance(payload["iat"], int):
            raise TokenValidationError(
                "Issued At (iat) claim must be a number present in the ID token"
            )

        # Nonce
        if nonce:
            if "nonce" not in payload or not isinstance(payload["nonce"], str):
                raise TokenValidationError(
                    "Nonce (nonce) claim must be a string present in the ID token"
                )
            if payload["nonce"] != nonce:
                raise TokenValidationError(
                    'Nonce (nonce) claim mismatch in the ID token; expected "{}", '
                    'found "{}"'.format(nonce, payload["nonce"])
                )

        # Organization
        if organization:
            if "org_id" not in payload or not isinstance(payload["org_id"], str):
                raise TokenValidationError(
                    "Organization (org_id) claim must be a string present in the ID"
                    " token"
                )
            if payload["org_id"] != organization:
                raise TokenValidationError(
                    "Organization (org_id) claim mismatch in the ID token; expected"
                    ' "{}", found "{}"'.format(organization, payload["org_id"])
                )

        # Authorized party
        if isinstance(payload["aud"], list) and len(payload["aud"]) > 1:
            if "azp" not in payload or not isinstance(payload["azp"], str):
                raise TokenValidationError(
                    "Authorized Party (azp) claim must be a string present in the ID"
                    " token when Audience (aud) claim has multiple values"
                )
            if payload["azp"] != self.aud:
                raise TokenValidationError(
                    "Authorized Party (azp) claim mismatch in the ID token; expected"
                    ' "{}", found "{}"'.format(self.aud, payload["azp"])
                )

        # Authentication time
        if max_age:
            if "auth_time" not in payload or not isinstance(payload["auth_time"], int):
                raise TokenValidationError(
                    "Authentication Time (auth_time) claim must be a number present in"
                    " the ID token when Max Age (max_age) is specified"
                )

            auth_valid_until = payload["auth_time"] + max_age + leeway
            if now > auth_valid_until:
                raise TokenValidationError(
                    "Authentication Time (auth_time) claim in the ID token indicates"
                    " that too much time has passed since the last end-user"
                    " authentication. Current time ({}) is after last auth at ({})".format(
                        now, auth_valid_until
                    )
                )
