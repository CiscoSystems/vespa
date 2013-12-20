# Copyright (c) 2013 Cisco Systems
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# @author: Henry Gessau, Cisco Systems

from collections import namedtuple

import json
import requests
from webob import exc as wexc

from neutron.plugins.ml2.drivers.cisco import exceptions as cexc

# Info about a MO's RN format and container class
MoPath = namedtuple('MoPath', ['container', 'rn_fmt'])

supported_mos = {
    'fvTenant': MoPath(None, 'tn-%s'),
    'fvBD': MoPath('fvTenant', 'BD-%s'),
    'fvRsBd': MoPath('fvAEPg', 'rsbd'),
    'fvSubnet': MoPath('fvBD', 'subnet-[%s]'),
    'fvCtx': MoPath('fvTenant', 'ctx-%s'),
    'fvRsCtx': MoPath('fvBD', 'rsctx'),
    'fvAp': MoPath('fvTenant', 'ap-%s'),
    'fvAEPg': MoPath('fvAp', 'epg-%s'),
    'fvRsProv': MoPath('fvAEPg', 'rsprov-%s'),
    'fvRsCons': MoPath('fvAEPg', 'rscons-%s'),

    'vzBrCP': MoPath('fvTenant', 'brc-%s'),
    'vzSubj': MoPath('vzBrCP', 'subj-%s'),
    'vzFilter': MoPath('fvTenant', 'flt-%s'),
    'vzRsFiltAtt': MoPath('vzSubj', 'rsfiltAtt-%s'),
    'vzEntry': MoPath('vzFilter', 'e-%s'),
    'vzInTerm': MoPath('vzSubj', 'intmnl'),
    'vzOutTerm': MoPath('vzSubj', 'outtmnl'),

    'vmmProvP': MoPath(None, 'vmmp-%s'),
    'vmmDomP': MoPath('vmmProvP', 'dom-%s'),
    'fvRsVmmDomAtt': MoPath('fvAEPg', 'rsvmmDomAtt-[%s]'),
}


class MoClass(object):

    def __init__(self, mo_class):
        global supported_mos
        self.mo_class = mo_class
        self.container = supported_mos[mo_class].container
        self.rn_fmt = supported_mos[mo_class].rn_fmt
        self.dn_fmt = self._dn_fmt()

    def _dn_fmt(self):
        """
        Recursively build the DN format using container and RN.

        Note: Call this method only once at init.
        """
        if self.container:
            return '/'.join([MoClass(self.container).dn_fmt, self.rn_fmt])
        return 'uni/' + self.rn_fmt

    def dn(self, *params):
        """Return the distinguished name for a managed object."""
        return self.dn_fmt % params

    @staticmethod
    def ux_name(*params):
        """Name for user-readable display in errors, logs, etc."""
        return ', '.join(params)  # TODO(Henry): something nicer?

    def attr(self, mo, key):
        return mo[0][self.mo_class]['attributes'][key]


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


def requestdata(request_func):
    """Decorator for REST requests.

    Before:
        Verify there is an authenticated session (logged in to APIC)
    After:
        Verify we got a response and it is HTTP OK.
        Extract the data from the response and return it.
    """
    def wrapper(self, *args, **kwargs):
        if not self.client.username and self.client.authentication:
            raise cexc.ApicSessionNotLoggedIn
        response = request_func(self, *args, **kwargs)
        if response is None:
            raise cexc.ApicHostNoResponse(url=args[0])
        imdata = unicode2str(response.json()).get('imdata')
        if response.status_code != wexc.HTTPOk.code:
            err_text = imdata[0]['error']['attributes']['text']
            raise cexc.ApicResponseNotOk(request=self.dn(*args),
                                        status_code=response.status_code,
                                        reason=response.reason, text=err_text)
        return imdata
    return wrapper


class ApicSession(object):

    def __init__(self, client):
        self.client = client
        self.api_base = client.api_base
        self.session = client.session

    @staticmethod
    def _make_data(key, **attrs):
        """Build the body for a msg out of a key and some attributes."""
        return json.dumps({key: {'attributes': attrs}})

    def _mo_names(self, mo_list):
        """Extract a list of just the names of the managed objects."""
        return [mo[self.mo_class]['attributes']['name'] for mo in mo_list]

    def _api_url(self, api):
        """Create the URL for a simple API."""
        return '%s/%s.json' % (self.api_base, api)

    def _mo_url(self, *args):
        """Create a URL for a MO lookup by DN."""
        dn = self.dn(*args)
        return '%s/mo/%s.json' % (self.api_base, dn)

    def _qry_url(self):
        """Create a URL for a query lookup by MO class."""
        return '%s/class/%s.json' % (self.api_base, self.mo_class)

    # REST requests

    @requestdata
    def get_data(self, request):
        """Retrieve generic data from the server."""
        url = self._api_url(request)
        return self.session.get(url)

    @requestdata
    def _get_mo(self, *args):
        """Retrieve a MO by DN."""
        url = self._mo_url(*args) + '?query-target=self'
        return self.session.get(url)

    @requestdata
    def _list_mo(self):
        """Retrieve the list of MOs for a class."""
        url = self._qry_url()
        return self.session.get(url)

    @requestdata
    def post_data(self, request, data):
        """Post generic data to the server."""
        url = self._api_url(request)
        return self.session.post(url, data=data)

    @requestdata
    def _post_mo(self, *args, **data):
        """Post data for MO to the server."""
        url = self._mo_url(*args)
        data = self._make_data(self.mo_class, **data)
        return self.session.post(url, data=data)


class MoClient(ApicSession, MoClass):

    def __init__(self, client, mo_class):
        ApicSession.__init__(self, client)
        MoClass.__init__(self, mo_class)

    def _ensure_status(self, mo, status):
        """Ensure that the status of a Managed Object is as expected."""
        if self.attr(mo, 'status') != status:
            name = self.attr(mo, 'name')
            raise cexc.ApicMoStatusChangeFailed(
                mo_class=self.mo_class, name=name, status=status)

    def _create_prereqs(self, *params):
        if self.container:
            prereq = MoClient(self.client, self.container)
            prereq.create(*(params[0: prereq.dn_fmt.count('%s')]))

    def create(self, *params, **attrs):
        self._create_prereqs(*params)
        try:
            # Use existing object if it's already created
            mo = self.get(*params)
        except cexc.ApicManagedObjectNotFound:
            mo = self._post_mo(*params, **attrs)
            self._ensure_status(mo, 'created')
        return mo

    def get(self, *params):
        mo = self._get_mo(*params)
        if not mo:
            raise cexc.ApicManagedObjectNotFound(
                klass=self.mo_class, name=self.ux_name(*params))
        return mo

    def list_all(self):
        mo_list = self._list_mo()
        return self._mo_names(mo_list)

    def update(self, *params, **attrs):
        self.get(*params)  # Raises if not found
        return self._post_mo(*params, **attrs)

    def delete(self, *params):
        try:
            self.get(*params)
        except cexc.ApicManagedObjectNotFound:
            return True
        mo = self._post_mo(*params, status='deleted')
        self._ensure_status(mo, 'deleted')
        return mo


class RestClient(ApicSession):
    """
    APIC REST client class.

    Attributes:
        api_base        e.g. 'http://10.2.3.45:8000/api'
        session         The session between client and controller
        authentication  Login info. None if not logged in to controller.
    """

    def __init__(self, host, port, usr=None, pwd=None, api='api', ssl=False):
        """Establish a session with the APIC."""
        protocol = ssl and 'https' or 'http'
        self.api_base = '%s://%s:%s/%s' % (protocol, host, port, api)
        self.session = requests.Session()

        # Initialize the session methods
        super(RestClient, self).__init__(self)

        # Log in
        self.authentication = None
        self.username = None
        if usr and pwd:
            self.login(usr, pwd)

        # Supported objects
        for mo_class in supported_mos:
            self.__dict__[mo_class] = MoClient(self, mo_class)

    def login(self, usr, pwd):
        """Log in to server. Save user name and authentication."""
        name_pwd = self._make_data('aaaUser', name=usr, pwd=pwd)
        self.authentication = self.post_data('aaaLogin', data=name_pwd)
        login_data = self.authentication[0]
        if login_data and 'error' in login_data:
            self.authentication = None
            raise cexc.ApicLoginFailed(user=usr)
        self.username = usr
        return self.authentication

    def logout(self):
        """End session with server."""
        if self.authentication and self.username:
            data = self._make_data('aaaUser', name=self.username)
            bye = self.post_data('aaaLogout', data=data)
            self.authentication = None
            self.username = None
            return bye
