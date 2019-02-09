
import hashlib
import json
import logging
from datetime import datetime, timedelta

import jwt
import requests
from oauthlib.common import generate_nonce
from requests_oauthlib import OAuth2Session

from galaxy.model import OIDCAccessToken, User
from ..authnz import IdentityProvider

log = logging.getLogger(__name__)
STATE_COOKIE_NAME = 'oidc-state'
NONCE_COOKIE_NAME = 'oidc-nonce'
DEFAULT_CLAIM_USERNAME = 'preferred_username'
DEFAULT_CLAIM_EMAIL = 'email'
DEFAULT_CLAIM_ID = 'sub'


class OIDCAuthnz(IdentityProvider):
    def __init__(self, provider, oidc_config, oidc_backend_config):
        self.config = {'provider': provider.lower()}
        self.config['verify_ssl'] = oidc_config['VERIFY_SSL']
        self.config['client_id'] = oidc_backend_config['client_id']
        self.config['client_secret'] = oidc_backend_config['client_secret']
        self.config['redirect_uri'] = oidc_backend_config['redirect_uri']
        # Either get OIDC config from well-known config URI or directly
        if 'well_known_oidc_config_uri' in oidc_backend_config:
            self.config['well_known_oidc_config_uri'] = oidc_backend_config['well_known_oidc_config_uri']
            well_known_oidc_config = self._load_well_known_oidc_config(
                self.config['well_known_oidc_config_uri'])
            self.config['authorization_endpoint'] = well_known_oidc_config['authorization_endpoint']
            self.config['token_endpoint'] = well_known_oidc_config['token_endpoint']
            self.config['userinfo_endpoint'] = well_known_oidc_config['userinfo_endpoint']
        else:
            self.config['authorization_endpoint'] = oidc_backend_config['authorization_endpoint']
            self.config['token_endpoint'] = oidc_backend_config['token_endpoint']
            self.config['userinfo_endpoint'] = oidc_backend_config['userinfo_endpoint']
        self.config['extra_params'] = oidc_backend_config.get('extra_params', None)
        self.config['userinfo_claim_mappings'] = oidc_backend_config.get('userinfo_claim_mappings', None)

    def authenticate(self, trans):
        base_authorize_url = self.config['authorization_endpoint']
        oauth2_session = self._create_oauth2_session()
        nonce = generate_nonce()
        nonce_hash = self._hash_nonce(nonce)
        extra_params = {"nonce": nonce_hash}
        if self.config['extra_params']:
            extra_params.update(self.config['extra_params'])
        authorization_url, state = oauth2_session.authorization_url(
            base_authorize_url, **extra_params)
        trans.set_cookie(value=state, name=STATE_COOKIE_NAME)
        trans.set_cookie(value=nonce, name=NONCE_COOKIE_NAME)
        return authorization_url

    def callback(self, state_token, authz_code, trans, login_redirect_url):
        # Take state value to validate from token. OAuth2Session.fetch_token
        # will validate that the state query parameter value on the URL matches
        # this value.
        state_cookie = trans.get_cookie(name=STATE_COOKIE_NAME)
        oauth2_session = self._create_oauth2_session(state=state_cookie)
        token = self._fetch_token(oauth2_session, trans)
        log.debug("token={}".format(json.dumps(token, indent=True)))
        access_token = token['access_token']
        id_token = token['id_token']
        refresh_token = token['refresh_token']
        expiration_time = datetime.now() + timedelta(seconds=token['expires_in'])
        refresh_expiration_time = datetime.now() + timedelta(seconds=token['refresh_expires_in'])

        # Get nonce from token['id_token'] and validate. 'nonce' in the
        # id_token is a hash of the nonce stored in the NONCE_COOKIE_NAME
        # cookie.
        id_token_decoded = jwt.decode(id_token, verify=False)
        nonce_hash = id_token_decoded['nonce']
        self._validate_nonce(trans, nonce_hash)

        # Get userinfo and lookup/create Galaxy user record
        userinfo = self._get_userinfo(oauth2_session)
        log.debug("userinfo={}".format(json.dumps(userinfo, indent=True)))
        claim_mappings = self._get_claim_mappings()
        username = userinfo[claim_mappings['username']]
        email = userinfo[claim_mappings['email']]
        user_id = userinfo[claim_mappings['id']]

        # Create or update oidc_access_token record
        oidc_access_token = self._get_oidc_access_token(trans.sa_session, user_id, self.config['provider'])
        if oidc_access_token is None:
            user = self._create_user(trans.sa_session, username, email)
            oidc_access_token = OIDCAccessToken(user=user,
                                                external_user_id=user_id,
                                                provider=self.config['provider'],
                                                access_token=access_token,
                                                id_token=id_token,
                                                refresh_token=refresh_token,
                                                expiration_time=expiration_time,
                                                refresh_expiration_time=refresh_expiration_time,
                                                raw_token=token)
        else:
            oidc_access_token.access_token = access_token
            oidc_access_token.id_token = id_token
            oidc_access_token.refresh_token = refresh_token
            oidc_access_token.expiration_time = expiration_time
            oidc_access_token.refresh_expiration_time = refresh_expiration_time
            oidc_access_token.raw_token = token
        trans.sa_session.add(oidc_access_token)
        trans.sa_session.flush()
        return login_redirect_url, oidc_access_token.user

    def disconnect(self, provider, trans, disconnect_redirect_url=None, association_id=None):
        # TODO: implement?
        pass

    def _create_oauth2_session(self, state=None):
        client_id = self.config['client_id']
        redirect_uri = self.config['redirect_uri']
        return OAuth2Session(client_id,
                             scope=('openid', 'email', 'profile'),
                             redirect_uri=redirect_uri,
                             state=state)

    def _fetch_token(self, oauth2_session, trans):
        client_secret = self.config['client_secret']
        token_endpoint = self.config['token_endpoint']
        return oauth2_session.fetch_token(
            token_endpoint,
            client_secret=client_secret,
            authorization_response=trans.request.url)

    def _get_userinfo(self, oauth2_session):
        userinfo_endpoint = self.config['userinfo_endpoint']
        return oauth2_session.get(userinfo_endpoint).json()
    
    def _get_claim_mappings(self):
        userinfo_claim_mappings = {
            'username': DEFAULT_CLAIM_USERNAME,
            'email': DEFAULT_CLAIM_EMAIL,
            'id': DEFAULT_CLAIM_ID
        }
        if self.config['userinfo_claim_mappings']:
            userinfo_claim_mappings.update(self.config['userinfo_claim_mappings'])
        return userinfo_claim_mappings

    def _get_oidc_access_token(self, sa_session, user_id, provider):
        return sa_session.query(OIDCAccessToken).filter_by(
            external_user_id=user_id, provider=provider).one_or_none()

    def _create_user(self, sa_session, username, email):
        user = User(email=email, username=username)
        user.set_random_password()
        sa_session.add(user)
        sa_session.flush()
        return user

    def _hash_nonce(self, nonce):
        return hashlib.sha256(nonce).hexdigest()

    def _validate_nonce(self, trans, nonce_hash):
        nonce_cookie = trans.get_cookie(name=NONCE_COOKIE_NAME)
        # Delete the nonce cookie
        trans.set_cookie('', name=NONCE_COOKIE_NAME, age=-1)
        nonce_cookie_hash = self._hash_nonce(nonce_cookie)
        if nonce_hash != nonce_cookie_hash:
            raise Exception("Nonce mismatch!")

    def _load_well_known_oidc_config(self, well_known_uri):
        return requests.get(well_known_uri).json()
