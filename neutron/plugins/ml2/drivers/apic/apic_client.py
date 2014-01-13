# Copyright (c) 2013, 2014 Cisco Systems
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
#
# TODO(Henry): Instantiate supported MOs on demand instead of creating all of
# them up front in the client.
#
# TODO(Henry): Instead of (*params, **attrs) arguments, maybe it is better to
# have (param_dict, attr_dict). This would force the caller to name all the
# params and attributes via keys in the dicts, and the client can do stricter
# checking of the arguments.
#
# TODO(Henry): Move the 'supported_mos' out of apic_client.py and instead
# provide an easy way for the user to add the list of MOs that they want to
# use. A library of MOs could be maintained somewhere?

from collections import namedtuple

import json
import logging
import requests
from webob import exc as wexc

from neutron.plugins.ml2.drivers.cisco import exceptions as cexc


LOG = logging.getLogger(__name__)


# Info about a MO's RN format and container class
class MoPath(namedtuple('MoPath', ['container', 'rn_fmt', 'can_create'])):
    def __new__(cls, container, rn_fmt, can_create=True):
        return super(MoPath, cls).__new__(cls, container, rn_fmt, can_create)

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
    'fvRsConsIf': MoPath('fvAEPg', 'rsconsif-%s'),
    'fvRsDomAtt': MoPath('fvAEPg', 'rsdomAtt-[%s]'),
    'fvRsPathAtt': MoPath('fvAEPg', 'rspathAtt-[%s]'),

    'vzBrCP': MoPath('fvTenant', 'brc-%s'),
    'vzSubj': MoPath('vzBrCP', 'subj-%s'),
    'vzFilter': MoPath('fvTenant', 'flt-%s'),
    'vzRsFiltAtt': MoPath('vzSubj', 'rsfiltAtt-%s'),
    'vzEntry': MoPath('vzFilter', 'e-%s'),
    'vzInTerm': MoPath('vzSubj', 'intmnl'),
    'vzOutTerm': MoPath('vzSubj', 'outtmnl'),
    'vzCPIf': MoPath('fvTenant', 'cif-%s'),
    'vzRsIf': MoPath('vzCPIf', 'rsif'),

    'vmmProvP': MoPath(None, 'vmmp-%s', False),
    'vmmDomP': MoPath('vmmProvP', 'dom-%s'),
    'vmmEpPD': MoPath('vmmDomP', 'eppd-[%s]'),

    'physDomP': MoPath(None, 'phys-%s'),

    'infra': MoPath(None, 'infra'),
    'infraNodeP': MoPath('infra', 'nprof-%s'),
    'infraLeafS': MoPath('infraNodeP', 'leaves-%s-typ-%s'),
    'infraNodeBlk': MoPath('infraLeafS', 'nodeblk-%s'),
    'infraRsAccPortP': MoPath('infraNodeP', 'rsaccPortP-[%s]'),
    'infraAccPortP': MoPath('infra', 'accportprof-%s'),
    'infraHPortS': MoPath('infraAccPortP', 'hports-%s-typ-%s'),
    'infraPortBlk': MoPath('infraHPortS', 'portblk-%s'),
    'infraRsAccBaseGrp': MoPath('infraHPortS', 'rsaccBaseGrp'),
    'infraFuncP': MoPath('infra', 'funcprof'),
    'infraAccPortGrp': MoPath('infraFuncP', 'accportgrp-%s'),
    'infraRsAttEntP': MoPath('infraAccPortGrp', 'rsattEntP'),
    'infraAttEntityP': MoPath('infra', 'attentp-%s'),
    'infraRsDomP': MoPath('infraAttEntityP', 'rsdomP-[%s]'),
    'infraRsVlanNs': MoPath('vmmDomP', 'rsvlanNs'),

    'fvnsVlanInstP': MoPath('infra', 'vlanns-%s-%s'),
    'fvnsEncapBlk__vlan': MoPath('fvnsVlanInstP', 'from-%s-to-%s'),
    'fvnsVxlanInstP': MoPath('infra', 'vxlanns-%s'),
    'fvnsEncapBlk__vxlan': MoPath('fvnsVxlanInstP', 'from-%s-to-%s'),
}


class MoClass(object):

    # Note(Henry): Yes, I am using a mutable default argument _inst_cache
    # here. It is not a design flaw, it is exactly what I want: for it to
    # persist for the life of MoClass to cache instances.
    # noinspection PyDefaultArgument
    def __new__(cls, mo_class, _inst_cache={}):
        """Ensure we create only one instance per mo_class."""
        try:
            return _inst_cache[mo_class]
        except KeyError:
            new_inst = super(MoClass, cls).__new__(cls)
            new_inst.__init__(mo_class)
            _inst_cache[mo_class] = new_inst
            return new_inst

    def __init__(self, mo_class):
        global supported_mos
        self.klass = mo_class
        self.klass_name = mo_class.split('__')[0]
        mo = supported_mos[mo_class]
        self.container = mo.container
        self.rn_fmt = mo.rn_fmt
        self.dn_fmt, self.params = self._dn_fmt()
        self.param_count = self.dn_fmt.count('%s')
        rn_has_param = self.rn_fmt.count('%s')
        self.can_create = rn_has_param and mo.can_create

    def _dn_fmt(self):
        """Recursively build the DN format using container and RN.

        Also make a list of the required parameters.
        Note: Call this method only once at init.
        """
        param = [self.klass] if '%s' in self.rn_fmt else []
        if self.container:
            container = MoClass(self.container)
            dn_fmt = '/'.join([container.dn_fmt, self.rn_fmt])
            params = container.params + param
            return dn_fmt, params
        return 'uni/' + self.rn_fmt, param

    def dn(self, *params):
        """Return the distinguished name for a managed object."""
        return self.dn_fmt % params


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
        if not self.client.authentication:
            raise cexc.ApicSessionNotLoggedIn
        url, data, response = request_func(self, *args, **kwargs)
        if response is None:
            raise cexc.ApicHostNoResponse(url=url)
        if data is None:
            request = url
        else:
            request = '%s, data=%s' % (url, data)
        imdata = unicode2str(response.json()).get('imdata')
        if response.status_code != wexc.HTTPOk.code:
            try:
                err_code = imdata[0]['error']['attributes']['code']
                err_text = imdata[0]['error']['attributes']['text']
            except (IndexError, KeyError):
                err_code = '[code for APIC error not found]'
                err_text = '[text for APIC error not found]'
            raise cexc.ApicResponseNotOk(request=request,
                                         status=response.status_code,
                                         reason=response.reason,
                                         err_text=err_text, err_code=err_code)
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

    def _api_url(self, api):
        """Create the URL for a generic API."""
        return '%s/%s.json' % (self.api_base, api)

    def _mo_url(self, mo, *args):
        """Create a URL for a MO lookup by DN."""
        dn = mo.dn(*args)
        return '%s/mo/%s.json' % (self.api_base, dn)

    def _qry_url(self, mo):
        """Create a URL for a query lookup by MO class."""
        return '%s/class/%s.json' % (self.api_base, mo.klass_name)

    # REST requests

    @requestdata
    def get_data(self, request):
        """Retrieve generic data from the server."""
        url = self._api_url(request)
        return url, None, self.session.get(url)

    @requestdata
    def _get_mo(self, mo, *args):
        """Retrieve a MO by DN."""
        url = self._mo_url(mo, *args) + '?query-target=self'
        return url, None, self.session.get(url)

    @requestdata
    def _list_mo(self, mo):
        """Retrieve the list of MOs for a class."""
        url = self._qry_url(mo)
        return url, None, self.session.get(url)

    @requestdata
    def post_data(self, request, data):
        """Post generic data to the server."""
        url = self._api_url(request)
        return url, data, self.session.post(url, data=data)

    @requestdata
    def _post_mo(self, mo, *args, **data):
        """Post data for MO to the server."""
        url = self._mo_url(mo, *args)
        data = self._make_data(mo.klass_name, **data)
        return url, data, self.session.post(url, data=data)


class MoManager(ApicSession):
    """CRUD operations on APIC Managed Objects."""

    def __init__(self, client, mo_class):
        super(MoManager, self).__init__(client)
        self.client = client
        self.mo = MoClass(mo_class)

    def _create_container(self, *params):
        """Recursively create all container objects."""
        if self.mo.container:
            container = MoManager(self.client, self.mo.container)
            if container.mo.can_create:
                container_params = params[0: container.mo.param_count]
                container._create_container(*container_params)
                container._post_mo(container.mo, *container_params)

    def create(self, *params, **attrs):
        self._create_container(*params)
        if self.mo.can_create:
            attrs['status'] = 'created'
        self._post_mo(self.mo, *params, **attrs)

    def _mo_attributes(self, obj_data):
        if (self.mo.klass_name in obj_data
                and 'attributes' in obj_data[self.mo.klass_name]):
            return obj_data[self.mo.klass_name]['attributes']

    def get(self, *params):
        """Return a dict of the MO's attributes, or None."""
        imdata = self._get_mo(self.mo, *params)
        if imdata:
            return self._mo_attributes(imdata[0])

    def list_all(self):
        imdata = self._list_mo(self.mo)
        return filter(None, [self._mo_attributes(obj) for obj in imdata])

    def list_names(self):
        return [obj['name'] for obj in self.list_all()]

    def update(self, *params, **attrs):
        self._post_mo(self.mo, *params, **attrs)

    def delete(self, *params):
        self._post_mo(self.mo, *params, status='deleted')


class RestClient(ApicSession):
    """
    APIC REST client class.

    Attributes:
        api_base        e.g. 'http://10.2.3.45:8000/api'
        session         The session between client and controller
        authentication  Login info. None if not logged in to controller.
    """

    def __init__(self, host, port=80, usr=None, pwd=None,
                 api='api', ssl=False):
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
            self.__dict__[mo_class] = MoManager(self, mo_class)

    def login(self, usr, pwd):
        """Log in to server. Save user name and authentication."""
        name_pwd = self._make_data('aaaUser', name=usr, pwd=pwd)
        self.authentication = 'trying'  # placate the request wrapper
        self.authentication = self.post_data('aaaLogin', data=name_pwd)
        self.username = usr
        return self.authentication

    def logout(self):
        """End session with server."""
        if not self.username:
            self.authentication = None
        if self.authentication:
            data = self._make_data('aaaUser', name=self.username)
            self.post_data('aaaLogout', data=data)
        self.authentication = None
