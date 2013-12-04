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


MO_TENANT = 'fvTenant'
MO_BD = 'fvBD'
MO_SUBNET = 'fvSubnet'
MO_AP = 'fvAp'
MO_EPG = 'fvAEPg'

MO_CONTRACT = 'vzBrCP'
MO_SUBJECT = 'vzSubj'
MO_FILTER = 'vzFilter'
MO_ENTRY = 'vzEntry'

mo_dn_fmt = {
    MO_TENANT: "uni/tn-%s",
    MO_BD: "uni/tn-%s/BD-%s",
    MO_SUBNET: "uni/tn-%s/BD-%s/subnet-[%s]",
    MO_AP: "uni/tn-%s/ap-%s",
    MO_EPG: "uni/tn-%s/ap-%s/epg-%s",
    MO_CONTRACT: "uni/tn-%s/brc-%s",
    MO_SUBJECT: "uni/tn-%s/brc-%s/subj-%s",
    MO_FILTER: "uni/tn-%s/flt-%s",
    MO_ENTRY: "uni/tn-%s/flt-%s/e-%s",
}


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
        raise cexc.ApicMoStatusChangeFailed(
            mo_class=mo_class, name=name, status=status)


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
            raise cexc.ApicSessionNotLoggedIn
        response = request_func(self, *args, **kwargs)
        if not response:
            raise cexc.ApicHostNoResponse(url=args[0])
        if response.status_code != wexc.HTTPOk.code:
            raise cexc.ApicResponseNotOk(request=args[0],
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

    @staticmethod
    def _mo_dn(mo_class, *args):
        """Return the distinguished name for a managed object class."""
        return mo_dn_fmt[mo_class] % args

    @staticmethod
    def _mo_names(mo_list, mo_class):
        """Extract a list of just the names of the managed objects."""
        return [mo[mo_class]['attributes']['name'] for mo in mo_list]

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
    def _get_mo(self, mo_class, *args):
        """Retrieve a MO by DN."""
        dn = self._mo_dn(mo_class, *args)
        return self.session.get(self._mo_url(dn) + '?query-target=self')

    @requestdata
    def _list_mo(self, mo_class):
        """Retrieve the list of MOs for a class."""
        return self.session.get(self._qry_url(mo_class))

    @requestdata
    def _post_data(self, request, data):
        """Post generic data to the server."""
        return self.session.post(self._api_url(request), data=data)

    @requestdata
    def _post_mo(self, mo_class, *args, **data):
        """Post data for MO to the server."""
        url = self._mo_url(self._mo_dn(mo_class, *args))
        data = self._make_data(mo_class, **data)
        return self.session.post(url, data=data)

    # Login and Logout

    def login(self, usr, pwd):
        """Log in to server. Save user name and authentication."""
        name_pwd = self._make_data('aaaUser', name=usr, pwd=pwd)
        self.authentication = self._post_data('aaaLogin', data=name_pwd)
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
            bye = self._post_data('aaaLogout', data=data)
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
            tenant = self._post_mo(MO_TENANT, tenant_id)
            ensure_status(tenant, MO_TENANT, 'created')
        return tenant

    def get_tenant(self, tenant_id):
        tenant = self._get_mo(MO_TENANT, tenant_id)
        if not tenant:
            raise ValueError("Tenant '%s' not found" % tenant_id)
        return tenant

    def list_tenants(self):
        ifc_tenants = self._list_mo(MO_TENANT)
        return self._mo_names(ifc_tenants, MO_TENANT)

    def update_tenant(self, tenant_id, **attrs):
        self.get_tenant(tenant_id)  # raises if tenant not found
        return self._post_mo(MO_TENANT, tenant_id, **attrs)

    def delete_tenant(self, tenant_id):
        try:
            self.get_tenant(tenant_id)
        except ValueError:
            return True
        tenant = self._post_mo(MO_TENANT, tenant_id, status='deleted')
        ensure_status(tenant, MO_TENANT, 'deleted')
        return tenant

    # Bridge Domains (networks in openstack)

    def create_bridge_domain(self, tenant_id, bd_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing BD if it's already created
            bridge_domain = self.get_bridge_domain(tenant_id, bd_id)
        except ValueError:
            bridge_domain = self._post_mo(MO_BD, tenant_id, bd_id)
            ensure_status(bridge_domain, MO_BD, 'created')
        return bridge_domain

    def get_bridge_domain(self, tenant_id, bd_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        bridge_domain = self._get_mo(MO_BD, tenant_id, bd_id)
        if not bridge_domain:
            raise ValueError("Bridge Domain '%s' not found" % bd_id)
        return bridge_domain

    def list_bridge_domains(self):
        bridge_domains = self._list_mo(MO_BD)
        return self._mo_names(bridge_domains, MO_BD)

    def update_bridge_domain(self, tenant_id, bd_id, **attrs):
        self.get_bridge_domain(tenant_id, bd_id)  # Raises if not found
        return self._post_mo(MO_BD, tenant_id, bd_id, **attrs)

    def delete_bridge_domain(self, tenant_id, bd_id):
        try:
            self.get_bridge_domain(tenant_id, bd_id)
        except ValueError:
            return True
        bridge_domain = self._post_mo(MO_BD, tenant_id, bd_id,
                                      status='deleted')
        ensure_status(bridge_domain, MO_BD, 'deleted')
        return bridge_domain

    # Subnets (gw_ip is a string: 'ip_address/mask')

    def create_subnet(self, tenant_id, bd_id, gw_ip):
        # Ensure tenant and BD exist (create them if needed)
        self.create_bridge_domain(tenant_id, bd_id)
        try:
            # Use existing subnet if it's already created
            subnet = self.get_subnet(tenant_id, bd_id, gw_ip)
        except ValueError:
            subnet = self._post_mo(MO_SUBNET, tenant_id, bd_id, gw_ip)
            ensure_status(subnet, MO_SUBNET, 'created')
        return subnet

    def get_subnet(self, tenant_id, bd_id, gw_ip):
        self.get_tenant(tenant_id)  # raises if tenant not found
        subnet = self._get_mo(MO_SUBNET, tenant_id, bd_id, gw_ip)
        if not subnet:
            raise ValueError("Subnet with gateway %s not found" % gw_ip)
        return subnet

    def list_subnets(self):
        subnets = self._list_mo(MO_SUBNET)
        return self._mo_names(subnets, MO_SUBNET)

    def update_subnet(self, tenant_id, bd_id, gw_ip, **attrs):
        self.get_subnet(tenant_id, bd_id, gw_ip)  # Raises if not found
        return self._post_mo(MO_SUBNET, tenant_id, bd_id, gw_ip, **attrs)

    def delete_subnet(self, tenant_id, bd_id, gw_ip):
        try:
            self.get_subnet(tenant_id, bd_id, gw_ip)
        except ValueError:
            return True
        subnet = self._post_mo(MO_SUBNET, tenant_id, bd_id, gw_ip,
                               status='deleted')
        ensure_status(subnet, MO_SUBNET, 'deleted')
        return subnet

    # Application Profiles

    def create_app_profile(self, tenant_id, ap_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing profile if it's already created
            profile = self.get_app_profile(tenant_id, ap_id)
        except ValueError:
            profile = self._post_mo(MO_AP, tenant_id, ap_id)
            ensure_status(profile, MO_AP, 'created')
        return profile

    def get_app_profile(self, tenant_id, ap_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        profile = self._get_mo(MO_AP, tenant_id, ap_id)
        if not profile:
            raise ValueError("App profile '%s' not found" % ap_id)
        return profile

    def list_app_profiles(self):
        ifc_app_profiles = self._list_mo(MO_AP)
        return self._mo_names(ifc_app_profiles, MO_AP)

    def update_app_profile(self, tenant_id, ap_id, **attrs):
        self.get_app_profile(tenant_id, ap_id)  # Raises if not found
        return self._post_mo(MO_AP, tenant_id, ap_id, **attrs)

    def delete_app_profile(self, tenant_id, ap_id):
        try:
            self.get_app_profile(tenant_id, ap_id)
        except ValueError:
            return True
        profile = self._post_mo(MO_AP, tenant_id, ap_id, status='deleted')
        ensure_status(profile, MO_AP, 'deleted')
        return profile

    # End-Point Groups

    def create_epg(self, tenant_id, ap_id, epg_id):
        # First ensure tenant and app profile exist (create them if not)
        self.create_app_profile(tenant_id, ap_id)
        try:
            # Use existing EPG if it's already created
            epg = self.get_epg(tenant_id, ap_id, epg_id)
        except ValueError:
            epg = self._post_mo(MO_EPG, tenant_id, ap_id, epg_id)
            ensure_status(epg, MO_EPG, 'created')
        return epg

    def get_epg(self, tenant_id, ap_id, epg_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        self.get_app_profile(tenant_id, ap_id)  # raises if ap_id not found
        epg = self._get_mo(MO_EPG, tenant_id, ap_id, epg_id)
        if not epg:
            raise ValueError("EPG '%s' not found" % epg_id)
        return epg

    def list_epgs(self):
        ifc_epgs = self._list_mo(MO_EPG)
        return self._mo_names(ifc_epgs, MO_EPG)

    def update_epg(self, tenant_id, ap_id, epg_id, **attrs):
        self.get_epg(tenant_id, ap_id, epg_id)  # Raises if not found
        return self._post_mo(MO_EPG, tenant_id, ap_id, epg_id, **attrs)

    def delete_epg(self, tenant_id, ap_id, epg_id):
        try:
            self.get_epg(tenant_id, ap_id, epg_id)
        except ValueError:
            return True
        epg = self._post_mo(MO_EPG, tenant_id, ap_id, epg_id, status='deleted')
        ensure_status(epg, MO_EPG, 'deleted')
        return epg

    # Contracts

    def create_contract(self, tenant_id, contract_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing contract if it's already created
            contract = self.get_contract(tenant_id, contract_id)
        except ValueError:
            contract = self._post_mo(MO_CONTRACT, tenant_id, contract_id)
            ensure_status(contract, MO_CONTRACT, 'created')
        return contract

    def get_contract(self, tenant_id, contract_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        contract = self._get_mo(MO_CONTRACT, tenant_id, contract_id)
        if not contract:
            raise ValueError("Contract '%s' not found" % contract_id)
        return contract

    def list_contracts(self):
        ifc_contracts = self._list_mo(MO_CONTRACT)
        return self._mo_names(ifc_contracts, MO_CONTRACT)
    
    def update_contract(self, tenant_id, contract_id, **attrs):
        self.get_contract(tenant_id, contract_id)  # Raises if not found
        return self._post_mo(MO_CONTRACT, tenant_id, contract_id, **attrs)

    def delete_contract(self, tenant_id, contract_id):
        try:
            self.get_contract(tenant_id, contract_id)
        except ValueError:
            return True
        contract = self._post_mo(MO_CONTRACT, tenant_id, contract_id,
                            status='deleted')
        ensure_status(contract, MO_CONTRACT, 'deleted')
        return contract

    # Subjects

    def create_subject(self, tenant_id, contract_id, subject_id):
        # First ensure the contract exists (create it if it doesn't)
        self.create_contract(tenant_id, contract_id)
        try:
            # Use existing subject if it's already created
            subject = self.get_subject(tenant_id, contract_id, subject_id)
        except ValueError:
            subject = self._post_mo(MO_SUBJECT, tenant_id, contract_id,
                                    subject_id)
            ensure_status(subject, MO_SUBJECT, 'created')
        return subject

    def get_subject(self, tenant_id, contract_id, subject_id):
        self.get_contract(tenant_id, contract_id)  # raises if not found
        subject = self._get_mo(MO_SUBJECT, tenant_id, contract_id, subject_id)
        if not subject:
            raise ValueError("Subject '%s' not found" % subject_id)
        return subject

    def list_subjects(self):
        ifc_subjects = self._list_mo(MO_SUBJECT)
        return self._mo_names(ifc_subjects, MO_SUBJECT)
    
    def update_subject(self, tenant_id, contract_id, subject_id, **attrs):
        self.get_subject(tenant_id, contract_id, subject_id)
        return self._post_mo(MO_SUBJECT, tenant_id, contract_id, subject_id,
                             **attrs)

    def delete_subject(self, tenant_id, contract_id, subject_id):
        try:
            self.get_subject(tenant_id, contract_id, subject_id)
        except ValueError:
            return True
        subject = self._post_mo(MO_SUBJECT, tenant_id, contract_id, subject_id,
                                status='deleted')
        ensure_status(subject, MO_SUBJECT, 'deleted')
        return subject

    # Filters

    def create_filter(self, tenant_id, filter_id):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing filter if it's already created
            filter_obj = self.get_filter(tenant_id, filter_id)
        except ValueError:
            filter_obj = self._post_mo(MO_FILTER, tenant_id, filter_id)
            ensure_status(filter_obj, MO_FILTER, 'created')
        return filter_obj

    def get_filter(self, tenant_id, filter_id):
        self.get_tenant(tenant_id)  # raises if tenant not found
        filter_obj = self._get_mo(MO_FILTER, tenant_id, filter_id)
        if not filter_obj:
            raise ValueError("filter '%s' not found" % filter_id)
        return filter_obj

    def list_filters(self):
        ifc_filters = self._list_mo(MO_FILTER)
        return self._mo_names(ifc_filters, MO_FILTER)
    
    def update_filter(self, tenant_id, filter_id, **attrs):
        self.get_filter(tenant_id, filter_id)  # Raises if not found
        return self._post_mo(MO_FILTER, tenant_id, filter_id, **attrs)

    def delete_filter(self, tenant_id, filter_id):
        try:
            self.get_filter(tenant_id, filter_id)
        except ValueError:
            return True
        filter_obj = self._post_mo(MO_FILTER, tenant_id, filter_id,
                                   status='deleted')
        ensure_status(filter_obj, MO_FILTER, 'deleted')
        return filter_obj

    # Entries

    def create_entry(self, tenant_id, contract_id, entry_id):
        # First ensure the contract exists (create it if it doesn't)
        self.create_contract(tenant_id, contract_id)
        try:
            # Use existing entry if it's already created
            entry = self.get_entry(tenant_id, contract_id, entry_id)
        except ValueError:
            entry = self._post_mo(MO_ENTRY, tenant_id, contract_id,
                                    entry_id)
            ensure_status(entry, MO_ENTRY, 'created')
        return entry

    def get_entry(self, tenant_id, contract_id, entry_id):
        self.get_contract(tenant_id, contract_id)  # raises if not found
        entry = self._get_mo(MO_ENTRY, tenant_id, contract_id, entry_id)
        if not entry:
            raise ValueError("Entry '%s' not found" % entry_id)
        return entry

    def list_entries(self):
        ifc_entries = self._list_mo(MO_ENTRY)
        return self._mo_names(ifc_entries, MO_ENTRY)

    def update_entry(self, tenant_id, contract_id, entry_id, **attrs):
        self.get_entry(tenant_id, contract_id, entry_id)
        return self._post_mo(MO_ENTRY, tenant_id, contract_id, entry_id,
                             **attrs)

    def delete_entry(self, tenant_id, contract_id, entry_id):
        try:
            self.get_entry(tenant_id, contract_id, entry_id)
        except ValueError:
            return True
        entry = self._post_mo(MO_ENTRY, tenant_id, contract_id, entry_id,
                                status='deleted')
        ensure_status(entry, MO_ENTRY, 'deleted')
        return entry


"""
# Work in progress...

class ManagedObject(RestClient):
    
    _mo_class = None

    def create(self, tenant_id, *params):
        # First ensure the tenant exists (create it if it doesn't)
        self.create_tenant(tenant_id)
        try:
            # Use existing object if it's already created
            mo = self.get(tenant_id, *params)
        except cexc.ApicManagedObjectNotFound:
            mo = self._post_mo(self._mo_class, tenant_id, *params)
            ensure_status(mo, self._mo_class, 'created')
        return mo

    def get(self, tenant_id, *params):
        self.get_tenant(tenant_id)  # raises if tenant not found
        mo = self._get_mo(self._mo_class, tenant_id, *params)
        if not mo:
            raise cexc.ApicManagedObjectNotFound(name=params[0])
        return mo

    def list_all(self):
        ifc_contracts = self._list_mo(MO_CONTRACT)
        return self._mo_names(ifc_contracts, MO_CONTRACT)
    
    def update(self, tenant_id, contract_id, **attrs):
        self.get_contract(tenant_id, contract_id)  # Raises if not found
        return self._post_mo(MO_CONTRACT, tenant_id, contract_id, **attrs)

    def delete(self, tenant_id, contract_id):
        try:
            self.get_contract(tenant_id, contract_id)
        except ValueError:
            return True
        contract = self._post_mo(MO_CONTRACT, tenant_id, contract_id,
                            status='deleted')
        ensure_status(contract, MO_CONTRACT, 'deleted')
        return contract
"""
