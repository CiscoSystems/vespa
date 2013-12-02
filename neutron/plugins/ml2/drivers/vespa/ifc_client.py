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

import json
import requests
from webob import exc as wexc

from neutron.plugins.ml2.drivers.cisco import exceptions as cexc


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


def ensure_status(mo, mo_class, status):
    """Ensure that the status of a Managed Object is as expected."""
    if mo[0][mo_class]['attributes']['status'] != status:
        name = mo[0][mo_class]['attributes']['name']
        raise cexc.IfcMoStatusChangeFailed(
            mo_class=mo_class, name=name, status=status)


IFC_TENANT = 'fvTenant'
IFC_BD = 'fvBD'
IFC_AP = 'fvAp'
IFC_EPG = 'fvAEPg'
IFC_SUBNET = 'fvSubnet'


def requestdata(request_func):
    """Decorator for REST requests.

    Before:
        Verify there is an authenticated session (logged in to IFC)
    After:
        Verify we got a response and it is HTTP OK.
        Extract the data from the response and return it.
    """
    def wrapper(self, *args, **kwargs):
        if not self.username and self.authentication:
            raise cexc.IfcSessionNotLoggedIn
        response = request_func(self, *args, **kwargs)
        if not response:
            raise cexc.IfcHostNoResponse(url=args[0])
        if response.status_code != wexc.HTTPOk.code:
            raise cexc.IfcResponseNotOk(request=args[0],
                                        status_code=response.status_code,
                                        reason=response.reason)
        return unicode2str(response.json()).get('imdata')
    return wrapper


class RestClient(object):
    """
    IFC REST client class.

    Attributes:
        api_base        e.g. 'http://10.2.3.45:8000/api'
        session         The session between client and controller
        authentication  Login info. None if not logged in to controller.
    """

    _mo_data = {
        IFC_TENANT: {
            'dn': "uni/tn-%s",
            'admins': ['admin', 'common', 'infra', 'mgmt'],
        },
        IFC_BD: {
            'dn': "uni/tn-%s/BD-%s",
            'admins': ['default', 'inb'],
        },
        IFC_SUBNET: {
            'dn': "uni/tn-%s/BD-%s/subnet-%s",
            'admins': [],
        },
        IFC_AP: {
            'dn': "uni/tn-%s/ap-%s",
            'admins': ['default', 'access'],
        },
        IFC_EPG: {
            'dn': "uni/tn-%s/ap-%s/epg-%s",
            'admins': ['default'],
        },
    }

    def __init__(self, host, port, usr=None, pwd=None, api='api', ssl=False):
        """docstring"""
        protocol = ssl and 'https' or 'http'
        self.api_base = '%s://%s:%s/%s' % (protocol, host, port, api)
        self.session = requests.Session()
        self.authentication = None
        self.username = None
        if usr and pwd:
            self.login(usr, pwd)

    # Internal methods for data and URL manipulation

    @staticmethod
    def _make_data(key, **attrs):
        """Build the body for a msg out of a key and some attributes."""
        return json.dumps({key: {'attributes': attrs}})

    def _mo_dn(self, mo_class, *args):
        """Return the distinguished name for a managed object class."""
        return self._mo_data[mo_class]['dn'] % args

    def _mo_names(self, mo_list, mo_class, include_admin=False):
        """Extract a list of just the names of the managed objects.

        Skip the IFC admin objects unless specifically asked for."""
        mo_names = []
        for mo in mo_list:
            mo_name = mo[mo_class]['attributes']['name']
            if (include_admin or
                    mo_name not in self._mo_data[mo_class]['admins']):
                mo_names.append(mo_name)
        return mo_names

    def _api_url(self, api):
        """Create the URL for a simple API."""
        return '%s/%s.json' % (self.api_base, api)

    def _mo_url(self, dn):
        """Create a URL for a MO lookup by DN."""
        return '%s/mo/%s.json' % (self.api_base, dn)

    def _qry_url(self, mo_class):
        """Create a URL for a query lookup by MO class."""
        return '%s/class/%s.json' % (self.api_base, mo_class)

    # REST requests
    @requestdata
    def get(self, request):
        """Retrieve data from the server."""
        return self.session.get(self._api_url(request))

    @requestdata
    def _get_mo(self, mo_class, *args):
        """Retrieve a MO by DN."""
        dn = self._mo_dn(mo_class, *args)
        return self.session.get(self._mo_url(dn) + '?query-target=self')

    @requestdata
    def _list_mo(self, mo_class):
        """Retrieve the list of MOs for a class."""
        return self.session.get(self._qry_url(mo_class))

    @requestdata
    def post(self, request, data):
        """Post generic data to the server."""
        return self.session.post(self._api_url(request), data=data)

    # Login and Logout

    @requestdata
    def _post_mo(self, mo_class, *args, **data):
        """Post data for MO to the server."""
        url = self._mo_url(self._mo_dn(mo_class, *args))
        data = self._make_data(mo_class, **data)
        return self.session.post(url, data=data)

    def login(self, usr, pwd):
        """Log in to server. Save user name and authentication."""
        name_pwd = self._make_data('aaaUser', name=usr, pwd=pwd)
        self.authentication = self.post('aaaLogin', data=name_pwd)
        login_data = self.authentication[0]
        if login_data and 'error' in login_data:
            self.authentication = None
            raise cexc.IfcLoginFailed(user=usr)
        self.username = usr
        return self.authentication

    def logout(self):
        """End session with server."""
        if self.authentication and self.username:
            data = self._make_data('aaaUser', name=self.username)
            bye = self.post('aaaLogout', data=data)
            self.authentication = None
            self.username = None
            return bye

    # ------- CRUDs --------
    # Create, Get, List, Update, Delete

    # Tenants

    def create_tenant(self, tenant_id):
        try:
            # Use existing tenant if it's already created
            tenant = self.get_tenant(tenant_id)
        except ValueError:
            tenant = self._post_mo(IFC_TENANT, tenant_id)
            ensure_status(tenant, IFC_TENANT, 'created')
        return tenant

    def get_tenant(self, tenant_id):
        tenant = self._get_mo(IFC_TENANT, tenant_id)
        if not tenant:
            raise ValueError("Tenant '%s' not found" % tenant_id)
        return tenant

    def list_tenants(self):
        ifc_tenants = self._list_mo(IFC_TENANT)
        return self._mo_names(ifc_tenants, IFC_TENANT)

    def update_tenant(self, tenant_id, **attrs):
        self.get_tenant(tenant_id)  # raises if tenant not found
        return self._post_mo(IFC_TENANT, tenant_id, **attrs)

    def delete_tenant(self, tenant_id):
        try:
            self.get_tenant(tenant_id)
        except ValueError:
            return True
        tenant = self._post_mo(IFC_TENANT, tenant_id, status='deleted')
        ensure_status(tenant, IFC_TENANT, 'deleted')
        return tenant

    # Bridge Domains (networks in openstack)

    def create_bridge_domain(self, tenant_id, bd_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing BD if it's already created
            bridge_domain = self.get_bridge_domain(bd_id, tenant_id)
        except ValueError:
            bridge_domain = self._post_mo(IFC_BD, tenant_id, bd_id)
            ensure_status(bridge_domain, IFC_BD, 'created')
        return bridge_domain

    def get_bridge_domain(self, tenant_id, bd_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        bridge_domain = self._get_mo(IFC_BD, tenant_id, bd_id)
        if not bridge_domain:
            raise ValueError("Bridge Domain '%s' not found" % bd_id)
        return bridge_domain

    def list_bridge_domains(self):
        bridge_domains = self._list_mo(IFC_BD)
        return self._mo_names(bridge_domains, IFC_BD)

    def update_bridge_domain(self, tenant_id, bd_id, **attrs):
        self.get_bridge_domain(tenant_id, bd_id)  # Raises if not found
        return self._post_mo(IFC_BD, tenant_id, bd_id, **attrs)

    def delete_bridge_domain(self, tenant_id, bd_id):
        try:
            self.get_bridge_domain(tenant_id, bd_id)
        except ValueError:
            return True
        bridge_domain = self._post_mo(IFC_BD, tenant_id, bd_id,
                                      status='deleted')
        ensure_status(bridge_domain, IFC_BD, 'deleted')
        return bridge_domain

    # Subnets

    def create_subnet(self, tenant_id, bd_id, gw_ip):
        # Ensure tenant and BD exist (create them if needed)
        self.create_bridge_domain(tenant_id, bd_id)
        try:
            # Use existing subnet if it's already created
            subnet = self.get_subnet(tenant_id, bd_id, gw_ip)
        except ValueError:
            subnet = self._post_mo(IFC_SUBNET, tenant_id, bd_id, gw_ip)
            ensure_status(subnet, IFC_SUBNET, 'created')
        return subnet

    def get_subnet(self, tenant_id, bd_id, gw_ip):
        self.get_tenant(tenant_id)  # raises if tenant not found
        subnet = self._get_mo(IFC_SUBNET, tenant_id, bd_id, gw_ip)
        if not subnet:
            raise ValueError("Subnet with gateway %s not found" % gw_ip)
        return subnet

    def list_subnets(self):
        subnets = self._list_mo(IFC_SUBNET)
        return self._mo_names(subnets, IFC_SUBNET)

    def update_subnet(self, tenant_id, bd_id, gw_ip, **attrs):
        self.get_subnet(tenant_id, bd_id, gw_ip)  # Raises if not found
        return self._post_mo(IFC_SUBNET, tenant_id, bd_id, gw_ip, **attrs)

    def delete_subnet(self, tenant_id, bd_id, gw_ip):
        try:
            self.get_subnet(tenant_id, bd_id, gw_ip)
        except ValueError:
            return True
        subnet = self._post_mo(IFC_SUBNET, tenant_id, bd_id, gw_ip,
                               status='deleted')
        ensure_status(subnet, IFC_SUBNET, 'deleted')
        return subnet

    # Application Profiles

    def create_app_profile(self, tenant_id, ap_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing profile if it's already created
            profile = self.get_app_profile(tenant_id, ap_id)
        except ValueError:
            profile = self._post_mo(IFC_AP, tenant_id, ap_id)
            ensure_status(profile, IFC_AP, 'created')
        return profile

    def get_app_profile(self, tenant_id, ap_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        profile = self._get_mo(IFC_AP, tenant_id, ap_id)
        if not profile:
            raise ValueError("App profile '%s' not found" % ap_id)
        return profile

    def list_app_profiles(self):
        ifc_app_profiles = self._list_mo(IFC_AP)
        return self._mo_names(ifc_app_profiles, IFC_AP)

    def update_app_profile(self, tenant_id, ap_id, **attrs):
        self.get_app_profile(tenant_id, ap_id)  # Raises if not found
        return self._post_mo(IFC_AP, tenant_id, ap_id, **attrs)

    def delete_app_profile(self, tenant_id, ap_id):
        try:
            self.get_app_profile(tenant_id, ap_id)
        except ValueError:
            return True
        profile = self._post_mo(IFC_AP, tenant_id, ap_id, status='deleted')
        ensure_status(profile, IFC_AP, 'deleted')
        return profile

    # End-Point Groups

    def create_epg(self, tenant_id, ap_id, epg_id):
        # First ensure tenant and app profile exist (create them if not)
        self.create_app_profile(tenant_id, ap_id)
        try:
            # Use existing EPG if it's already created
            epg = self.get_epg(tenant_id, ap_id, epg_id)
        except ValueError:
            epg = self._post_mo(IFC_EPG, tenant_id, ap_id, epg_id)
            ensure_status(epg, IFC_EPG, 'created')
        return epg

    def get_epg(self, tenant_id, ap_id, epg_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        self.get_app_profile(tenant_id, ap_id)  # raises if ap_id not found
        epg = self._get_mo(IFC_EPG, tenant_id, ap_id, epg_id)
        if not epg:
            raise ValueError("EPG '%s' not found" % epg_id)
        return epg

    def list_epgs(self):
        ifc_epgs = self._list_mo(IFC_EPG)
        return self._mo_names(ifc_epgs, IFC_EPG)

    def update_epg(self, tenant_id, ap_id, epg_id, **attrs):
        self.get_epg(tenant_id, ap_id, epg_id)  # Raises if not found
        return self._post_mo(IFC_EPG, tenant_id, ap_id, epg_id, **attrs)

    def delete_epg(self, tenant_id, ap_id, epg_id):
        try:
            self.get_epg(tenant_id, ap_id, epg_id)
        except ValueError:
            return True
        epg = self._post_mo(IFC_EPG, tenant_id, ap_id, epg_id,
                            status='deleted')
        ensure_status(epg, IFC_EPG, 'deleted')
        return epg
