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

from neutron.db import api as db_api
from neutron.db import model_base
from neutron.openstack.common import log
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.apic import apic_client
from neutron.plugins.ml2.drivers.apic import config
from neutron.plugins.ml2.drivers.apic.apic_manager import APICManager

LOG = log.getLogger(__name__)


class APICMechanismDriver(api.MechanismDriver):
    def initialize(self):
        self.apic_manager = APICManager()
        # TODO: Create a VMM domain and VLAN namespace
        

    def create_port_precommit(self, context):
        # Get tenant details from port context
        tenant_id = context.current['tenant_id']
        self.apic_manager.ensure_tenant_created_on_apic(tenant_id)

        # Get network
        network = context.network.current['id']

        # Get host binding if any
        host = context.current['binding:host_id']

        # Get port mac
        mac = context.current['mac_address']
        
        # Check if port is bound to a host
        if not host:
            # Not a VM port, return for now
            return

        # Check for an EPG for this network

    def create_port_postcommit(self, context):
        pass

    def create_network_precommit(self, context):
        net_id = context.current['id']
        tenant_id = context.current['tenant_id']
        
        self.apic_manager.ensure_bd_created_on_apic(tenant_id, net_id)
        # Create EPG for this network
        self.apic_manager.ensure_epg_created_for_network(tenant_id, net_id)

    def create_network_postcommit(self, context):
        pass

    def delete_network_precommit(self, context):
        net_id = context.current['id']
        tenant_id = context.current['tenant_id']

        self.apic_manager.delete_bd_on_apic(tenant_id, net_id)
        self.apic_manager.delete_epg_for_network(tenant_id, net_id)

    def create_subnet_precommit(self, context):
        tenant_id = context.current['tenant_id']
        network_id = context.current['network_id']
        subnet_id = context.current['id']
        gateway_ip = context.current['gateway_ip']
        cidr = context.current['cidr']
        netmask = re.sub(r"^.+\/",'', cidr)
        gateway_ip = gateway_ip + '/' + netmask

        self.apic_manager.ensure_subnet_created_on_apic(tenant_id, network_id,
                                                        subnet_id, gateway_ip)

    def create_subnet_postcommit(self, context):
        pass
