# Copyright (c) 2014 Cisco Systems Inc.
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
import uuid

from oslo.config import cfg

from neutron.plugins.ml2.drivers.apic import apic_client
from neutron.plugins.ml2.drivers.apic import apic_model
from neutron.plugins.ml2.drivers.apic import config

AP_NAME = 'openstack'
VMM_DOMAIN = 'openstack'
PROVIDER_NAME = 'openstack_provider'
CONSUMER_NAME = 'openstack_consumer'


def group_by_ranges(i):
    """Group a list of numbers into tuples representing contiguous ranges."""
    i.sort()
    for a, b in itertools.groupby(enumerate(i), lambda (x, y): y - x):
        b = list(b)
        yield b[0][1], b[-1][1]


class APICManager(object):
    def __init__(self):
        self.db = apic_model.ApicDbModel()

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

    def ensure_infra_created_on_apic(self):
        # Loop over switches
        for switch in self.switch_dict:
            # Create a node profile for this switch
            self.ensure_node_profile_created_for_switch(switch)

            # Check if a port profile exists for this node
            sprofile = self.db.get_port_profile_for_node(switch)
            if not sprofile:
                # Generate uuid for port profile name
                ppname = uuid.uuid4()
                # Create port profile for this switch
                pprofile = self.ensure_port_profile_created_on_apic(ppname)
                # Add port profile to node profile
                ppdn = pprofile['dn']
                self.apic.infraRsAccPortP.create(switch, ppdn)
            else:
                ppname = sprofile.profile_id

            # Gather port ranges for this switch
            ports = self.switch_dict[switch]
            # Gather common modules
            modules = {}
            for port in ports:
                module, sw_port = port.split('/')
                if module not in modules:
                    modules[module] = []
                modules[module].append(int(sw_port))
            # Sort modules and convert to ranges if possible
            for module in modules:
                profile = self.db.get_profile_for_module(switch, ppname,
                                                         module)
                if not profile:
                    # Create host port selector for this module
                    hname = uuid.uuid4()
                    self.apic.infraHPortS.create(ppname, hname, 'range')
                    # Add relation to the function profile
                    fpdn = self.function_profile['dn']
                    self.apic.infraRsAccBaseGrp.create(ppname, hname, 'range',
                                                       tDn=fpdn)
                    modules[module].sort()
                else:
                    hname = profile.hpselc_id

                ranges = group_by_ranges(modules[module])
                # Add this module and ports to the profile
                for prange in ranges:
                    # Check if this port block is already added to the profile
                    if not self.db.get_profile_for_module_and_ports(
                            switch, ppname, module, prange[0], prange[-1]):
                        # Create port block for this port range
                        pbname = uuid.uuid4()
                        self.apic.infraPortBlk.create(ppname, hname, 'range',
                                                      pbname, fromCard=module,
                                                      toCard=module,
                                                      fromPort=str(prange[0]),
                                                      toPort=str(prange[-1]))
                        # Add DB row
                        self.db.add_profile_for_module_and_ports(
                            switch, ppname, hname, module,
                            prange[0], prange[-1])

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
            self.node_profiles[switch_id] = {
                'object': self.apic.infraNodeP.get(switch_id)
            }
        else:
            self.node_profiles[switch_id] = {
                'object': sobj
            }

    def ensure_port_profile_created_on_apic(self, name):
        self.apic.infraAccPortP.create(name)
        return self.apic.infraAccPortP.get(name)

    def ensure_vmm_domain_created_on_apic(self, vmm_name,
                                          vlan_ns=None, vxlan_ns=None):
        provider = cfg.CONF.ml2_apic.apic_vmm_provider
        self.vmm_domain = self.apic.vmmDomP.get(provider, vmm_name)
        if not self.vmm_domain:
            provider = cfg.CONF.ml2_apic.apic_vmm_provider
            self.apic.vmmDomP.create(provider, vmm_name)
            if vlan_ns:
                vlan_ns_dn = vlan_ns['dn']
                self.apic.infraRsVlanNs.create(provider, vmm_name,
                                               tDn=vlan_ns_dn)
            elif vxlan_ns:
                # TODO(asomya): Add VXLAN bits bere
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
            vlan_encap = self.apic.fvnsEncapBlk__vlan.get(*ns_blk_args)
            if not vlan_encap:
                ns_kw_args = {
                    'name': 'encap',
                    'from': vlan_min,
                    'to': vlan_max
                }
                self.apic.fvnsEncapBlk__vlan.create(*ns_blk_args, **ns_kw_args)
            self.vlan_ns = self.apic.fvnsVlanInstP.get(*ns_args)
        return self.vlan_ns

    def ensure_tenant_created_on_apic(self, tenant_id):
        """Make sure a tenant exists on the APIC.

        Check the local tenant cache and create a new tenant
        if not found
        """
        if not self.apic.fvTenant.get(tenant_id):
            self.apic.fvTenant.create(tenant_id)
            self.apic_tenants.append(tenant_id)

    def ensure_bd_created_on_apic(self, tenant_id, bd_id):
        if bd_id not in self.apic_bridge_domains:
            self.apic.fvBD.create(tenant_id, bd_id)
            self.apic_bridge_domains.append(bd_id)
            # Add default context to the BD
            self.apic.fvRsCtx.create(tenant_id, bd_id, tnFvCtxName='default')

    def delete_bd_on_apic(self, tenant_id, bd_id):
        self.apic.fvBD.delete(tenant_id, bd_id)

    def ensure_subnet_created_on_apic(self, tenant_id, bd_id,
                                      subnet_id, gw_ip):
        if subnet_id not in self.apic_subnets:
            self.apic.fvSubnet.create(tenant_id, bd_id, gw_ip)
            self.apic_subnets.append(subnet_id)

    def ensure_filter_created_on_apic(self, tenant_id, filter_id):
        if filter_id not in self.apic_filters:
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
            if network_id in epg:
                pass
            for security_group in security_groups:
                # Compare security groups
                if security_group in epg:
                    pass

    def create_epg_with_net_and_secgroups(self, network_id,
                                          security_groups):
        pass

    def ensure_epg_created_for_network(self, tenant_id, network_id, net_name):
        # Check if an EPG is already present for this network
        epg = self.db.get_epg_for_network(network_id)
        if epg:
            return epg

        # Create a new EPG on the APIC
        epg_uid = '-'.join([str(net_name), str(uuid.uuid4())])
        self.apic.fvAEPg.create(tenant_id, AP_NAME, epg_uid)

        # Add bd to EPG
        bd = self.apic.fvBD.get(tenant_id, network_id)
        bd_name = bd['name']

        # create fvRsBd
        self.apic.fvRsBd.create(tenant_id, AP_NAME, epg_uid,
                                tnFvBDName=bd_name)

        # Add VMM to EPG
        dom_cloud = self.apic.vmmDomP.get('VMware', 'openstack')
        vmm_dn = dom_cloud['dn']
        self.apic.fvRsDomAtt.create(tenant_id, AP_NAME, epg_uid, vmm_dn)

        # Get EPG to read the segmentation id
        self.apic.fvAEPg.get(tenant_id, AP_NAME, epg_uid)

        # Stick it in the DB
        # TODO(asomya): use the real segmentation id
        epg = self.db.write_epg_for_network(network_id, epg_uid,
                                            segmentation_id='1')
        return epg

    def delete_epg_for_network(self, tenant_id, network_id):
        # Check if an EPG is already present for this network
        epg = self.db.get_epg_for_network(network_id)
        if not epg:
            return False

        # Delete this epg
        self.apic.fvAEPg.delete(tenant_id, AP_NAME, epg.epg_id)
        # Remove DB row
        self.db.delete_epg(epg)

    def create_tenant_filter(self, tenant_id):
        fuuid = uuid.uuid4()
        # Create a new tenant filter
        self.apic.vzFilter.create(tenant_id, fuuid)
        # Create a new entry
        euuid = uuid.uuid4()
        self.apic.vzEntry.create(tenant_id, fuuid, euuid)

        return fuuid

    def set_contract_for_epg(self, tenant_id, epg_id,
                             contract_id, provider=False):
        if provider:
            self.apic.fvRsProv.create(tenant_id, AP_NAME, epg_id, contract_id)
            self.db.set_provider_contract(epg_id)
            self.make_tenant_contract_global(tenant_id)
        else:
            self.apic.fvRsCons.create(tenant_id, AP_NAME, epg_id, contract_id)

    def delete_contract_for_epg(self, tenant_id, epg_id,
                                contract_id, provider=False):
        if provider:
            self.apic.fvRsProv.delete(tenant_id, AP_NAME, epg_id, contract_id)
            self.db.unset_provider_contract(epg_id)
            # Pick out another EPG to set as contract provider
            epg = self.db.get_an_epg(epg_id)
            self.update_contract_for_epg(tenant_id, epg.epg_id,
                                         contract_id, True)
        else:
            self.apic.fvRsCons.delete(tenant_id, AP_NAME, epg_id, contract_id)

    def update_contract_for_epg(self, tenant_id, epg_id,
                                contract_id, provider=False):
        self.apic.fvRsCons.delete(tenant_id, AP_NAME, epg_id, contract_id)
        self.set_contract_for_epg(tenant_id, epg_id, contract_id, provider)

    def create_tenant_contract(self, tenant_id):
        contract = self.db.get_contract_for_tenant(tenant_id)
        if not contract:
            cuuid = uuid.uuid4()
            # Create contract
            self.apic.vzBrCP.create(tenant_id, cuuid, scope='tenant')
            acontract = self.apic.vzBrCP.get(tenant_id, cuuid)
            # Create subject
            suuid = uuid.uuid4()
            self.apic.vzSubj.create(tenant_id, cuuid, suuid)
            # Create filter and entry
            tfilter = self.create_tenant_filter(tenant_id)
            # Create interm and outterm
            self.apic.vzInTerm.create(tenant_id, cuuid, suuid)
            self.apic.vzRsFiltAtt__In.create(tenant_id, cuuid, suuid, tfilter)
            self.apic.vzOutTerm.create(tenant_id, cuuid, suuid)
            self.apic.vzRsFiltAtt__Out.create(tenant_id, cuuid, suuid, tfilter)
            # Create contract interface
            iuuid = uuid.uuid4()
            self.apic.vzCPIf.create(tenant_id, iuuid)
            self.apic.vzRsIf.create(tenant_id, iuuid, tDn=acontract['dn'])
            # Store contract in DB
            contract = self.db.write_contract_for_tenant(tenant_id,
                                                         cuuid, tfilter)

        return contract

    def make_tenant_contract_global(self, tenant_id):
        contract = self.db.get_contract_for_tenant(tenant_id)
        self.apic.vzBrCP.update(tenant_id, contract.contract_id,
                                scope='global')

    def ensure_path_created_for_port(self, tenant_id, network_id,
                                     host_id, encap, net_name):
        encap = 'vlan-' + str(encap)
        epg = self.ensure_epg_created_for_network(tenant_id, network_id,
                                                  net_name)
        eid = epg.epg_id

        # Get attached switch and port for this host
        switch, port = config.get_switch_and_port_for_host(host_id)
        pdn = 'topology/pod-1/paths-%s/pathep-[eth%s]' % (switch, port)

        # Check if exists
        patt = self.apic.fvRsPathAtt.get(tenant_id, AP_NAME, eid, pdn)
        if not patt:
            self.apic.fvRsPathAtt.create(tenant_id, AP_NAME, eid, pdn,
                                         encap=encap, mode="regular")
