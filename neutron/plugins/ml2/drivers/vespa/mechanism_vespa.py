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
import re

from oslo.config import cfg

from neutron.openstack.common import log
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.vespa import ifc_client
from neutron.plugins.ml2.drivers.vespa.type_vespa import VespaTypeDriver


LOG = log.getLogger(__name__)


class Epg(object):
    def __init__(self):
        pass


class Tenant(object):
    def __init__(self):
        pass


class AppProfile(object):
    def __init__(self):
        pass


class IFCManager(object):
    def __init__(self):
        # Connect to the the IFC
        host = cfg.CONF.ml2_vespa.ifc_host
        port = cfg.CONF.ml2_vespa.ifc_port
        username = cfg.CONF.ml2_vespa.ifc_username
        password = cfg.CONF.ml2_vespa.ifc_password
        self.ifc = ifc_client.RestClient(host, port, username, password)

        # Update lists of managed objects from the IFC
        self.ifc_tenants = self.ifc.tenant.list_all()
        self.ifc_bridge_domains = self.ifc.bridge_domain.list_all()
        self.ifc_subnets = self.ifc.subnet.list_all()
        self.ifc_app_profiles = self.ifc.app_profile.list_all()
        self.ifc_epgs = self.ifc.epg.list_all()
        self.ifc_filters = self.ifc.filter.list_all()

    def ensure_tenant_created_on_ifc(self, tenant_id):
        """Make sure a tenant exists on the IFC.

        Check the local tenant cache and create a new tenant 
        if not found
        """
        if not tenant_id in self.ifc_tenants:
            self.ifc.tenant.create(tenant_id)
            self.ifc_tenants.append(tenant_id)

    def ensure_bd_created_on_ifc(self, tenant_id, bd_id):
        if not bd_id in self.ifc_bridge_domains:
            self.ifc.bridge_domain.create(tenant_id, bd_id)
            self.ifc_bridge_domains.append(bd_id)

    def delete_bd_on_ifc(self, tenant_id, bd_id):
        self.ifc.bridge_domain.delete(tenant_id, bd_id)

    def ensure_subnet_created_on_ifc(self, tenant_id, bd_id, subnet_id, gw_ip):
        if not subnet_id in self.ifc_subnets:
            self.ifc.subnet.create(tenant_id, bd_id, gw_ip)
            self.ifc_subnets.append(subnet_id)

    def ensure_filter_created_on_ifc(self, tenant_id, filter_id):
        if not filter_id in self.ifc_filters:
            self.ifc.filter.create(tenant_id, filter_id)
            self.ifc_filters.append(filter_id)

    def get_epg_list_from_ifc(self):
        """Get a list of all EPG's from the IFC."""
        self.ifc_epgs = self.ifc.epg.list_all()

    def search_for_epg_with_net_and_secgroups(self, network_id,
                                              security_groups):
        """Search the list of cached EPGs for a match."""
        for epg in self.ifc_epgs:
            # Compare network
            for security_group in security_groups:
                # Compare security groups
                pass

    def create_epg_with_net_and_secgroups(self, network_id,
                                          security_groups):
        pass


class VespaMechanismDriver(api.MechanismDriver):
    def initialize(self):
        self.type_driver = VespaTypeDriver()
        self.ifc_manager = IFCManager()

    def create_port_precommit(self, context):
        # Get tenant details from port context
        tenant_id = context.current['tenant_id']
        self.ifc_manager.ensure_tenant_created_on_ifc(tenant_id)

        # Get network
        network = context.network.current['id']

        # Get host binding if any
        host = context.current['binding:host_id']

        # Get port mac
        mac = context.current['mac_address']
        
        # Check if port is bound to a host
        if host:
            # Get or Reserve a segment for this network/host combo
            seg = self.type_driver._check_and_allocate_segment_for_network(
                    network, host)
        else:
            # Not a VM port, return for now
            return

        # Get security groups for the port
        secgrps = context.current['security_groups']

        # Ensure all security groups are created on the IFC
        for secgrp in secgrps:
            self.ifc_manager.ensure_filter_created_on_ifc(tenant_id, secgrp)
            # Ensure entries have been created for each rule

        # Check if the combination of security group + network exists
        # already  as an EPG
        epg = self.ifc_manager.search_for_epg_with_net_and_secgroups(network,
                                                                     secgrps)

        if not epg:
            # Create a new EPG with this network and security group
            epg = self.ifc_manager.create_epg_with_net_and_secgroups(network,
                                                                     secgrps)
    def create_port_postcommit(self, context):
        pass

    def create_network_precommit(self, context):
        net_id = context.current['id']
        tenant_id = context.current['tenant_id']
        
        self.ifc_manager.ensure_bd_created_on_ifc(tenant_id, net_id)

    def create_network_postcommit(self, context):
        pass

    def delete_network_precommit(self, context):
        net_id = context.current['id']
        tenant_id = context.current['tenant_id']

        self.ifc_manager.delete_bd_on_ifc(tenant_id, net_id)

    def create_subnet_precommit(self, context):
        tenant_id = context.current['tenant_id']
        network_id = context.current['network_id']
        subnet_id = context.current['id']
        gateway_ip = context.current['gateway_ip']
        cidr = context.current['cidr']
        netmask = re.sub(r"^.+\/",'', cidr)
        gateway_ip = gateway_ip + '/' + netmask

        self.ifc_manager.ensure_subnet_created_on_ifc(tenant_id, network_id,
                                                      subnet_id, gateway_ip)

    def create_subnet_postcommit(self, context):
        pass
