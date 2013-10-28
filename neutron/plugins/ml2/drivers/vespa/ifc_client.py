# Copyright (c) 2013 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import requests
from webob import exc as wexc


def unicode2str(data):
    """
    Recursively convert all unicode strings to byte strings in data.

    This converter is intended for use with data that has been decoded from
    a json stream, so it only recurses into dictionaries and lists.
    """
    if isinstance(data, dict):
        return {unicode2str(k): unicode2str(v) for k, v in data.iteritems()}
    elif isinstance(data, list):
        return [unicode2str(e) for e in data]
    elif isinstance(data, unicode):
        return data.encode('utf-8')
    else:
        return data


TN_CLASS = 'fvTenant'
BD_CLASS = 'fvBD'
AP_CLASS = 'fvAp'
EPG_CLASS = 'fvAEPg'
SUBNET_CLASS = 'fvSubnet'


def tn_dn(tenant_id):
    return "uni/tn-%s" % tenant_id


def bd_dn(tenant_id, network_id):
    return "%s/BD-%s" % (tn_dn(tenant_id), network_id)


def ap_dn(tenant_id, ap_id):
    return "%s/ap-%s" % (tn_dn(tenant_id), ap_id)


def epg_dn(tenant_id, ap_id, epg_id):
    return "%s/epg-%s" % (ap_dn(tenant_id, ap_id), epg_id)


class RestClient(object):
    """
    docstring

    Attributes:
        api_base        e.g. 'http://10.2.3.45:8000/api'
        session         The session between client and controller
        authentication  Login info. None if not logged in to controller.
    """

    fmt = 'json'

    def __init__(self, host, port, usr=None, pwd=None, api='api', ssl=False):
        """docstring"""
        protocol = ssl and 'https' or 'http'
        self.api_base = '%s://%s:%s/%s' % (protocol, host, port, api)
        self.session = requests.Session()
        # TODO: check that session is OK
        self.authentication = None
        self.username = None
        if usr and pwd:
            self.login(usr, pwd)
            # TODO: check for successful login

    def _make_data(self, key, **attrs):
        """Build the body for a msg out of a key and some attributes."""
        if self.fmt == 'json':
            return json.dumps({key: {'attributes': attrs}})
        elif self.fmt == 'xml':
            raise NotImplementedError
        else:
            raise NotImplementedError

    def _get_data(self, response):
        """Extract and decode the data from the body of a response."""
        if self.fmt == 'json':
            data = unicode2str(response.json()).get('imdata')
            # data = json.loads(response.content)
            return data
        elif self.fmt == 'xml':
            raise NotImplementedError
        else:
            raise NotImplementedError

    def _api_url(self, api):
        """Create the URL for a simple API."""
        return '%s/%s.%s' % (self.api_base, api, self.fmt)

    def _mo_url(self, dn):
        """Create a URL for a MO lookup by DN."""
        return '%s/mo/%s.%s' % (self.api_base, dn, self.fmt)

    # TODO: get() and post() require valid session and login

    def get(self, request):
        """Retrieve data from the server."""
        response = self.session.get(self._api_url(request))
        data = self._get_data(response)
        return response, data

    def get_mo(self, dn):
        """Retrieve a MO by DN."""
        response = self.session.get(self._mo_url(dn) + '?query-target=self')
        imdata = self._get_data(response)
        return response, imdata

    def post(self, request, data):
        """Post generic data to the server."""
        reponse = self.session.post(self._api_url(request), data=data)
        imdata = self._get_data(reponse)
        return reponse, imdata

    def post_mo(self, request, data):
        """Post data for MO to the server."""
        reponse = self.session.post(self._mo_url(request), data=data)
        imdata = self._get_data(reponse)
        return reponse, imdata

    def login(self, usr, pwd):
        """Log in to server. Save user name and authentication."""
        name_pwd = self._make_data('aaaUser', name=usr, pwd=pwd)
        rsp, self.authentication = self.post('aaaLogin', data=name_pwd)
        if not rsp:
            print "ERROR: NO RESPONSE FROM SERVER"
            self.authentication = None
            return
        if rsp.status_code != wexc.HTTPOk.code:
            print "ERROR: SERVER RESPONSE CODE", rsp.status_code
            self.authentication = None
            return
        login_data = self.authentication[0]
        if login_data:
            if 'error' in login_data:
                print 'ERROR: FAILED TO LOG IN'
                self.authentication = None
                return
        self.username = usr
        return self.authentication

    def logout(self):
        """End session with server."""
        if self.authentication and self.username:
            data = self._make_data('aaaUser', name=self.username)
            rsp, bye = self.post('aaaLogout', data=data)
            if rsp and rsp.status_code == wexc.HTTPOk.code and rsp.ok:
                self.authentication = None
                self.username = None
                return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Useful for 'with RestClient() as:' contexts."""
        self.logout()

    # ------- CRUDs --------

    # TODO: decorate CRUDs with authentication verifier
    @staticmethod
    def _verify_response(response, operation):
        # TODO: this should raise RestServerErrors
        if not response:
            raise ValueError("%s: No response from server" % operation)
        if response.status_code != wexc.HTTPOk.code:
            raise ValueError("%s: Server returned status code %d" %
                             (operation, response.status_code))

    # Tenants

    def create_tenant(self, tenant_id):
        try:
            # Use existing tenant if it's already created
            tenant = self.get_tenant(tenant_id)
        except ValueError:
            data = self._make_data(TN_CLASS)
            rsp, tenant = self.post_mo(tn_dn(tenant_id), data=data)
            self._verify_response(rsp, 'create_tenant(%s)' % tenant_id)
        return tenant

    def get_tenant(self, tenant_id):
        rsp, tenant = self.get_mo(tn_dn(tenant_id))
        self._verify_response(rsp, 'get_tenant(%s)' % tenant_id)
        if not tenant:
            raise ValueError("Tenant '%s' not found" % tenant_id)
        return tenant

    def update_tenant(self, tenant_id, **attrs):
        self.get_tenant(tenant_id)  # raises if tenant not found
        data = self._make_data(TN_CLASS, attrs)
        rsp, tenant = self.post_mo(tn_dn(tenant_id), data=data)
        self._verify_response(rsp, 'update_tenant(%s)' % tenant_id)
        return tenant

    def delete_tenant(self, tenant_id):
        try:
            self.get_tenant(tenant_id)
        except ValueError:
            return True
        data = self._make_data(TN_CLASS, status='deleted')
        rsp, tenant = self.post_mo(tn_dn(tenant_id), data=data)
        self._verify_response(rsp, 'delete_tenant(%s)' % tenant_id)
        return tenant

    # Networks

    def create_network(self, tenant_id, network_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing network if it's already created
            network = self.get_network(network_id, tenant_id)
        except ValueError:
            data = self._make_data(BD_CLASS)
            rsp, network = self.post_mo(bd_dn(tenant_id, network_id),
                                        data=data)
            self._verify_response(rsp, 'create_network(%s)' % network_id)
        return network

    def get_network(self, tenant_id, network_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        rsp, network = self.get_mo(bd_dn(tenant_id, network_id))
        self._verify_response(rsp, 'get_network(%s)' % network_id)
        if not network:
            raise ValueError("Network '%s' not found" % network_id)
        return network

    def update_network(self, tenant_id, network_id, **attrs):
        self.get_network(tenant_id, network_id)  # Raises if not found
        data = self._make_data(BD_CLASS, attrs)
        rsp, network = self.post_mo(bd_dn(tenant_id, network_id),
                                    data=data)
        self._verify_response(rsp, 'update_network(%s)' % network_id)
        return network

    def delete_network(self, tenant_id, network_id):
        try:
            self.get_network(tenant_id, network_id)
        except ValueError:
            return True
        data = self._make_data(BD_CLASS, status='deleted')
        rsp, network = self.post_mo(bd_dn(tenant_id, network_id), data=data)
        self._verify_response(rsp, 'delete_network(%s)' % network_id)
        return network

    # Application Profiles

    def create_app_profile(self, tenant_id, ap_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing profile if it's already created
            profile = self.get_app_profile(tenant_id, ap_id)
        except ValueError:
            data = self._make_data(AP_CLASS)
            rsp, profile = self.post_mo(ap_dn(tenant_id, ap_id), data=data)
            self._verify_response(rsp, 'create_ap(%s)' % ap_id)
        return profile

    def get_app_profile(self, tenant_id, ap_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        rsp, profile = self.get_mo(ap_dn(tenant_id, ap_id))
        self._verify_response(rsp, 'get_ap(%s)' % ap_id)
        if not profile:
            raise ValueError("App profile '%s' not found" % ap_id)
        return profile

    def update_app_profile(self, tenant_id, ap_id, **attrs):
        self.get_app_profile(tenant_id, ap_id)  # Raises if not found
        data = self._make_data(AP_CLASS, attrs)
        rsp, profile = self.post_mo(ap_dn(tenant_id, ap_id), data=data)
        self._verify_response(rsp, 'update_ap(%s)' % ap_id)
        return profile

    def delete_app_profile(self, tenant_id, ap_id):
        try:
            self.get_app_profile(tenant_id, ap_id)
        except ValueError:
            return True
        data = self._make_data(AP_CLASS, status='deleted')
        rsp, profile = self.post_mo(ap_dn(tenant_id, ap_id), data=data)
        self._verify_response(rsp, 'delete_ap(%s)' % ap_id)
        return profile

    # End-Point Groups

    def create_epg(self, tenant_id, ap_id, epg_id):
        # First ensure tenant and app profile exist (create them if not)
        self.create_app_profile(tenant_id, ap_id)
        try:
            # Use existing EPG if it's already created
            epg = self.get_epg(tenant_id, ap_id, epg_id)
        except ValueError:
            data = self._make_data(EPG_CLASS)
            rsp, epg = self.post_mo(epg_dn(tenant_id, ap_id, epg_id),
                                    data=data)
            self._verify_response(rsp, 'create_epg(%s)' % epg_id)
        return epg

    def get_epg(self, tenant_id, ap_id, epg_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        self.get_app_profile(tenant_id, ap_id)  # raises if ap_id not found
        rsp, epg = self.get_mo(epg_dn(tenant_id, ap_id, epg_id))
        self._verify_response(rsp, 'get_epg(%s)' % epg_id)
        if not epg:
            raise ValueError("EPG '%s' not found" % epg_id)
        return epg

    def update_epg(self, tenant_id, ap_id, epg_id, **attrs):
        self.get_epg(tenant_id, ap_id, epg_id)  # Raises if not found
        data = self._make_data(EPG_CLASS, attrs)
        rsp, epg = self.post_mo(epg_dn(tenant_id, ap_id, epg_id), data=data)
        self._verify_response(rsp, 'update_epg(%s)' % epg_id)
        return epg

    def delete_epg(self, tenant_id, ap_id, epg_id):
        try:
            self.get_epg(tenant_id, ap_id, epg_id)
        except ValueError:
            return True
        data = self._make_data(EPG_CLASS, status='deleted')
        rsp, epg = self.post_mo(epg_dn(tenant_id, ap_id, epg_id), data=data)
        self._verify_response(rsp, 'delete_epg(%s)' % epg_id)
        return epg
