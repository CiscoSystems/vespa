# Copyright (c) 2013 Cisco Systems Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Arvind Somya (asomya@cisco.com), Cisco Systems Inc.

import itertools
import sqlalchemy as sa
import uuid

from oslo.config import cfg

from neutron.db import api as db_api
from neutron.db import model_base
from neutron.openstack.common import log
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.apic import apic_client
from neutron.plugins.ml2.drivers.apic import config

AP_NAME = 'openstack'
VMM_DOMAIN = 'openstack'

class NetworkEPG(model_base.BASEV2):
    """EPG's created on the apic per network"""

    __tablename__ = 'ml2_apic_epgs'

    network_id = sa.Column(sa.String(64), nullable=False,
                           primary_key=True)
    epg_id = sa.Column(sa.String(64), nullable=False)
    segmentation_id = sa.Column(sa.String(64), nullable=False)

class PortProfile(model_base.BASEV2):
    """Port profiles created on the APIC"""

    __tablename__ = 'ml2_apic_port_profiles'

    node_id = sa.Column(sa.String(64), nullable=False, primary_key=True)
    profile_id = sa.Column(sa.String(64), nullable=False)
    hpselc_id = sa.Column(sa.String(64), nullable=False)
    module = sa.Column(sa.String(10), nullable=False)
    from_port = sa.Column(sa.Integer(10), nullable=False)
    to_port = sa.Column(sa.Integer(10), nullable=False)

class APICManager(object):
    def __init__(self):
        config.ML2MechApicConfig()
        self.switch_dict = config.ML2MechApicConfig.switch_dict
        # Connect to the the APIC
        host = cfg.CONF.ml2_apic.apic_host
        port = cfg.CONF.ml2_apic.apic_port
        username = cfg.CONF.ml2_apic.apic_username
        password = cfg.CONF.ml2_apic.apic_password
        self.apic = apic_client.RestClient(host, port, username, password)

        # Update lists of managed objects from the APIC
        self.apic_tenants = self.apic.fvTenant.list_names()
        self.apic_bridge_domains = self.apic.fvBD.list_names()
        self.apic_subnets = self.apic.fvSubnet.list_names()
        self.apic_app_profiles = self.apic.fvAp.list_names()
        self.apic_epgs = self.apic.fvAEPg.list_names()
        self.apic_filters = self.apic.vzFilter.list_names()
        self.port_profiles = {}
        self.vmm_domain = None
        self.vlan_ns = None
        self.node_profiles = {}
        self.entity_profile = None
        self.function_profile = None

    def _to_range(self, i):
        i.sort()
        for a, b in itertools.groupby(enumerate(i), lambda (x, y): y - x):
            b = list(b)
            yield b[0][1], b[-1][1]

    def get_port_profile_for_node(self, node_id):
        session = db_api.get_session()
        return session.query(PortProfile).filter_by(node_id=node_id).first()

    def get_profile_for_module_and_ports(self, node_id, profile_id,
                                         module, from_port, to_port):
        session = db_api.get_session()
        return session.query(PortProfile).filter_by(node_id=node_id,
                                                    module=module,
                                                    profile_id=profile_id,
                                                    from_port=from_port,
                                                    to_port=to_port).first()

    def get_profile_for_module(self, node_id, profile_id, module):
        session = db_api.get_session()
        return session.query(PortProfile).filter_by(node_id=node_id,
                                                    profile_id=profile_id,
                                                    module=module).first()

    def add_profile_for_module_and_ports(self, node_id, profile_id, hpselc_id,
                                         module, from_port, to_port):
        session = db_api.get_session()
        row = PortProfile(node_id=node_id, profile_id=profile_id,
                          hpselc_id=hpselc_id, module=module,
                          from_port=from_port, to_port=to_port)
        session.add(row)
        session.flush()

    def ensure_infra_created_on_apic(self):
        # Loop over switches
        for switch in self.switch_dict.keys():
            # Create a node profile for this switch
            self.ensure_node_profile_created_for_switch(switch)

            # Check if a port profile exists for this node
            ppname = None
            if not self.get_port_profile_for_node(switch):
                # Generate uuid for port profile name
                ppname = uuid.uuid4()
                # Create port profile for this switch
                pprofile = self.ensure_port_profile_created_on_apic(ppname)
                # Add port profile to node profile
                ppdn = pprofile['dn']
                self.apic.infraRsAccPortP.create(switch, ppdn)
            else:
                ppname = self.get_port_profile_for_node(switch).profile_id

            # Gather port ranges for this switch
            ports = self.switch_dict[switch].keys()
            # Gather common modules
            modules = {}
            for port in ports:
                module, sw_port = port.split('/')
                if not module in modules:
                    modules[module] = []
                modules[module].append(int(sw_port))
            # Sort modules and convert to ranges if possible
            for module in modules:
                hname = None
                if not self.get_profile_for_module(switch, ppname, module):
                    # Create host port selector for this module
                    hname = uuid.uuid4()
                    hpselc = self.apic.infraHPortS.create(ppname, hname, 'range')
                    # Add relation to the function profile
                    fpdn = self.function_profile['dn']
                    self.apic.infraRsAccBaseGrp.create(ppname, hname, 'range', tDn=fpdn)
                    modules[module].sort()
                else:
                    hname = self.get_profile_for_module(switch, ppname, module).hpselc_id

                ranges = self._to_range(modules[module])
                # Add this module and ports to the profile
                for prange in ranges:
                    # Check if this port block is already added to the profile
                    if not self.get_profile_for_module_and_ports(
                           switch, ppname, module, prange[0], prange[-1]):
                        # Create port block for this port range
                        pbname = uuid.uuid4()
                        self.apic.infraPortBlk.create(ppname, hname, 'range',
                                                      pbname, fromCard=module,
                                                      toCard=module,
                                                      fromPort=str(prange[0]),
                                                      toPort=str(prange[-1]))
                        # Add DB row
                        self.add_profile_for_module_and_ports(switch, 
                                                              ppname, hname,
                                                              module, prange[0],
                                                              prange[-1])

    def ensure_entity_profile_created_on_apic(self, name):
        self.entity_profile = self.apic.infraAttEntityP.get(name)
        if not self.entity_profile:
            vmm_dn = self.vmm_domain['dn']
            self.apic.infraAttEntityP.create(name)
            # Attach vmm domain to entity profile
            self.apic.infraRsDomP.create(name, vmm_dn)
            self.entity_profile = self.apic.infraAttEntityP.get(name)

    def ensure_function_profile_created_on_apic(self, name):
        self.function_profile = self.apic.infraAccPortGrp.get(name)
        if not self.function_profile:
            self.apic.infraAccPortGrp.create(name)
            # Attach entity profile to function profile
            entp_dn = self.entity_profile['dn']
            self.apic.infraRsAttEntP.create(name, tDn=entp_dn)
            self.function_profile = self.apic.infraAccPortGrp.get(name)
            
    def ensure_node_profile_created_for_switch(self, switch_id):
        sobj = self.apic.infraNodeP.get(switch_id)
        if not sobj:
            # Create Node profile
            self.apic.infraNodeP.create(switch_id)
            # Create leaf selector
            lswitch_id = uuid.uuid4()
            self.apic.infraLeafS.create(switch_id, lswitch_id, 'range')
            # Add leaf nodes to the selector
            name = uuid.uuid4()
            self.apic.infraNodeBlk.create(switch_id, lswitch_id, 'range',
                                          name, from_=switch_id, to_=switch_id)
            self.node_profiles[switch_id] = {}
            self.node_profiles[switch_id]['object'] = self.apic.infraNodeP.get(switch_id)
        else:
            self.node_profiles[switch_id] = {}
            self.node_profiles[switch_id]['object'] = sobj

    def ensure_port_profile_created_on_apic(self, name):
        self.apic.infraAccPortP.create(name)
        return self.apic.infraAccPortP.get(name)

    def ensure_vmm_domain_created_on_apic(self, vmm_name, vlan_ns=None, vxlan_ns=None):
        provider = cfg.CONF.ml2_apic.apic_vmm_provider
        self.vmm_domain = self.apic.vmmDomP.get(provider, vmm_name)
        if not self.vmm_domain:
            provider = cfg.CONF.ml2_apic.apic_vmm_provider
            self.apic.vmmDomP.create(provider, vmm_name)
            if vlan_ns:
                vlan_ns_dn = vlan_ns['dn']
                self.apic.infraRsVlanNs.create(provider, vmm_name, tDn=vlan_ns_dn)
            elif vxlan_ns:
                # TODO: (asomya) Add VXLAN bits bere
                pass
            self.vmm_domain = self.apic.vmmDomP.get(provider, vmm_name)

    def ensure_vlan_ns_created_on_apic(self, name, vlan_min, vlan_max):
        ns_args = name, 'static'
        self.vlan_ns = self.apic.fvnsVlanInstP.get(*ns_args)
        if not self.vlan_ns:
            self.apic.fvnsVlanInstP.create(*ns_args)
            vlan_min = 'vlan-' + vlan_min
            vlan_max = 'vlan-' + vlan_max
            ns_blk_args = name, 'static', vlan_min, vlan_max
            self.vlan_encap = self.apic.fvnsEncapBlk__vlan.get(*ns_blk_args)
            if not self.vlan_encap:
                ns_kw_args = {'name': 'encap', 'from': vlan_min, 'to': vlan_max}
                self.apic.fvnsEncapBlk__vlan.create(*ns_blk_args, **ns_kw_args)
            return self.apic.fvnsVlanInstP.get(*ns_args)

    def ensure_node_profile_created_on_apic(self, name):
        if not self.node_profile:
            self.apic.infraNodeP.create(name)
            self.node_profile = self.apic.infraNodeP.get(name)

    def ensure_tenant_created_on_apic(self, tenant_id):
        """Make sure a tenant exists on the APIC.

        Check the local tenant cache and create a new tenant 
        if not found
        """
        if not tenant_id in self.apic_tenants:
            self.apic.fvTenant.create(tenant_id)
            self.apic_tenants.append(tenant_id)

    def ensure_bd_created_on_apic(self, tenant_id, bd_id):
        if not bd_id in self.apic_bridge_domains:
            self.apic.fvBD.create(tenant_id, bd_id)
            self.apic_bridge_domains.append(bd_id)
            # Add default context to the BD
            self.apic.fvRsCtx.create(tenant_id, bd_id, tnFvCtxName='default')

    def delete_bd_on_apic(self, tenant_id, bd_id):
        self.apic.fvBD.delete(tenant_id, bd_id)

    def ensure_subnet_created_on_apic(self, tenant_id, bd_id, subnet_id, gw_ip):
        if not subnet_id in self.apic_subnets:
            self.apic.fvSubnet.create(tenant_id, bd_id, gw_ip)
            self.apic_subnets.append(subnet_id)

    def ensure_filter_created_on_apic(self, tenant_id, filter_id):
        if not filter_id in self.apic_filters:
            self.apic.vzFilter.create(tenant_id, filter_id)
            self.apic_filters.append(filter_id)

    def get_epg_list_from_apic(self):
        """Get a list of all EPG's from the APIC."""
        self.apic_epgs = self.apic.fvAEPg.list_names()

    def search_for_epg_with_net_and_secgroups(self, network_id,
                                              security_groups):
        """Search the list of cached EPGs for a match."""
        for epg in self.apic_epgs:
            # Compare network
            for security_group in security_groups:
                # Compare security groups
                pass

    def create_epg_with_net_and_secgroups(self, network_id,
                                          security_groups):
        pass

    def ensure_epg_created_for_network(self, tenant_id, network_id):
        # Check if an EPG is already present for this network
        session = db_api.get_session()
        epg = session.query(NetworkEPG).filter_by(network_id=network_id).first()
        if epg:
            return epg

        # Create a new EPG on the APIC
        epg_uid = str(uuid.uuid4())
        self.apic.fvAEPg.create(tenant_id, AP_NAME, epg_uid)

        # Add bd to EPG
        bd = self.apic.fvBD.get(tenant_id, network_id)
        bd_name = bd['name']

        # create fvRsBd
        self.apic.fvRsBd.create(tenant_id, AP_NAME, epg_uid, tnFvBDName=bd_name)

        # Add VMM to EPG
        dom_cloud = self.apic.vmmDomP.get('VMware', 'openstack')
        vmm_dn = dom_cloud['dn']
        self.apic.fvRsDomAtt.create(tenant_id, AP_NAME, epg_uid, vmm_dn)

        # Get EPG to read the segmentation id
        epgm = self.apic.fvAEPg.get(tenant_id, AP_NAME, epg_uid)

        # Stick it in the DB, TEMP use a dummy seg id
        epg = NetworkEPG(network_id=network_id, epg_id=epg_uid, segmentation_id='1')
        session.add(epg)
        session.flush()

    def delete_epg_for_network(self, tenant_id, network_id):
        # Check if an EPG is already present for this network
        session = db_api.get_session()
        epg = session.query(NetworkEPG).filter_by(network_id=network_id).first()
        if not epg:
            return False

        # Delete this epg
        self.apic.fvAEPg.delete(tenant_id, AP_NAME, epg.epg_id)
        # Remove DB row
        session.delete(epg)
        session.flush()

    def _get_switch_and_port_for_host(self, host_id):
        for switch in self.switch_dict.keys():
            for port in self.switch_dict[switch].keys():
                if host_id in self.switch_dict[switch][port]:
                    return (switch, port)

    def ensure_path_created_for_port(self, tenant_id, network_id, host_id, encap):
        encap = 'vlan-' + str(encap)
        epg = self.ensure_epg_created_for_network(tenant_id, network_id)
        eid = epg.epg_id

        # Get attached switch and port for this host
        switch, port = self._get_switch_and_port_for_host(host_id)
        pdn = 'topology/pod-1/paths-%s/pathep-[eth%s]' % (switch, port)

        # Check if exists
        patt = self.apic.fvRsPathAtt.get(tenant_id, AP_NAME, eid, pdn)
        if not patt:
            self.apic.fvRsPathAtt.create(tenant_id, AP_NAME, eid, pdn,
                                         encap=encap, mode="regular")
