from .base import AuthenticationBase
from .client_authentication import add_client_authentication


class GetToken(AuthenticationBase):

    """/oauth/token related endpoints

    Args:
        domain (str): Your auth0 domain (e.g: username.auth0.com)
    """

    def authorization_code(
        self,
        code,
        redirect_uri,
        grant_type="authorization_code",
    ):
        """Authorization code grant

        This is the OAuth 2.0 grant that regular web apps utilize in order
        to access an API. Use this endpoint to exchange an Authorization Code
        for a Token.

        Args:
            code (str): The Authorization Code received from the /authorize Calls

            redirect_uri (str, optional): This is required only if it was set at
            the GET /authorize endpoint. The values must match

            grant_type (str): Denotes the flow you're using. For authorization code
            use authorization_code

        Returns:
            access_token, id_token
        """

        return self.authenticated_post(
            f"{self.protocol}://{self.domain}/oauth/token",
            data={
                "client_id": self.client_id,
                "code": code,
                "grant_type": grant_type,
                "redirect_uri": redirect_uri,
            },
        )

    def authorization_code_pkce(
        self,
        code_verifier,
        code,
        redirect_uri,
        grant_type="authorization_code",
    ):
        """Authorization code pkce grant

        This is the OAuth 2.0 grant that mobile apps utilize in order to access an API.
        Use this endpoint to exchange an Authorization Code for a Token.

        Args:
            code_verifier (str): Cryptographically random key that was used to generate
            the code_challenge passed to /authorize.

            code (str): The Authorization Code received from the /authorize Calls

            redirect_uri (str, optional): This is required only if it was set at
            the GET /authorize endpoint. The values must match

            grant_type (str): Denotes the flow you're using. For authorization code pkce
            use authorization_code

        Returns:
            access_token, id_token
        """

        return self.post(
            f"{self.protocol}://{self.domain}/oauth/token",
            data={
                "client_id": self.client_id,
                "code_verifier": code_verifier,
                "code": code,
                "grant_type": grant_type,
                "redirect_uri": redirect_uri,
            },
        )

    def client_credentials(
        self,
        audience,
        grant_type="client_credentials",
    ):
        """Client credentials grant

        This is the OAuth 2.0 grant that server processes utilize in
        order to access an API. Use this endpoint to directly request
        an access_token by using the Application Credentials (a Client Id and
        a Client Secret).

        Args:
            audience (str): The unique identifier of the target API you want to access.

            grant_type (str, optional): Denotes the flow you're using. For client credentials use "client_credentials"

        Returns:
            access_token
        """

        return self.authenticated_post(
            f"{self.protocol}://{self.domain}/oauth/token",
            data={
                "client_id": self.client_id,
                "audience": audience,
                "grant_type": grant_type,
            },
        )

    def login(
        self,
        username,
        password,
        scope,
        realm,
        audience,
        grant_type="http://auth0.com/oauth/grant-type/password-realm",
    ):
        """Calls /oauth/token endpoint with password-realm grant type


        This is the OAuth 2.0 grant that highly trusted apps utilize in order
        to access an API. In this flow the end-user is asked to fill in credentials
        (username/password) typically using an interactive form in the user-agent
        (browser). This information is later on sent to the client and Auth0.
        It is therefore imperative that the client is absolutely trusted with
        this information.

        Args:
            audience (str): The unique identifier of the target API you want to access.

            username (str): Resource owner's identifier

            password (str): resource owner's Secret

            scope(str): String value of the different scopes the client is asking for.
            Multiple scopes are separated with whitespace.

            realm (str): String value of the realm the user belongs.
            Set this if you want to add realm support at this grant.

            grant_type (str, optional): Denotes the flow you're using. For password realm
            use http://auth0.com/oauth/grant-type/password-realm

        Returns:
            access_token, id_token
        """

        return self.authenticated_post(
            f"{self.protocol}://{self.domain}/oauth/token",
            data={
                "client_id": self.client_id,
                "username": username,
                "password": password,
                "realm": realm,
                "scope": scope,
                "audience": audience,
                "grant_type": grant_type,
            },
        )

    def refresh_token(
        self,
        refresh_token,
        scope="",
        grant_type="refresh_token",
    ):
        """Calls /oauth/token endpoint with refresh token grant type

        Use this endpoint to refresh an access token, using the refresh token you got during authorization.

        Args:
            refresh_token (str): The refresh token returned from the initial token request.

            scope (str): Use this to limit the scopes of the new access token.
            Multiple scopes are separated with whitespace.

            grant_type (str): Denotes the flow you're using. For refresh token
            use refresh_token

        Returns:
            access_token, id_token
        """

        return self.authenticated_post(
            f"{self.protocol}://{self.domain}/oauth/token",
            data={
                "client_id": self.client_id,
                "refresh_token": refresh_token,
                "scope": scope,
                "grant_type": grant_type,
            },
        )

    def passwordless_login(self, username, otp, realm, scope, audience):
        """Calls /oauth/token endpoint with http://auth0.com/oauth/grant-type/passwordless/otp grant type

        Once the verification code was received, login the user using this endpoint with their
        phone number/email and verification code.

        Args:
            username (str): The user's phone number or email address.

            otp (str): the user's verification code.

            realm (str): use 'sms' or 'email'.
            Should be the same as the one used to start the passwordless flow.

            scope(str): String value of the different scopes the client is asking for.
            Multiple scopes are separated with whitespace.

            audience (str): The unique identifier of the target API you want to access.

        Returns:
            access_token, id_token
        """

        return self.authenticated_post(
            f"{self.protocol}://{self.domain}/oauth/token",
            data={
                "client_id": self.client_id,
                "username": username,
                "otp": otp,
                "realm": realm,
                "scope": scope,
                "audience": audience,
                "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
            },
        )
