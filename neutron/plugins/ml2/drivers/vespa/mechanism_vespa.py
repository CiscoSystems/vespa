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
        self.ifc_tenants = self.ifc.list_tenants()
        self.ifc_networks = self.ifc.list_networks()
        self.ifc_app_profiles = self.ifc.list_app_profiles()
        self.ifc_epgs = self.ifc.list_epgs()

    def ensure_tenant_created_on_ifc(self, tenant_id):
        """Make sure a tenant exists on the IFC.

        Check the local tenant cache and create a new tenant 
        if not found
        """
        if not tenant_id in self.ifc_tenants:
            self.create_tenant_on_ifc(tenant_id)

    def create_tenant_on_ifc(self, tenant_id):
        """Create an Openstack tenant on the IFC."""
        self.ifc.create_tenant(tenant_id)

    def get_epg_list_from_ifc(self):
        """Get a list of all EPG's from the IFC"""
        self.ifc_epgs = self.ifc.list_epgs()


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

    def create_port_postcommit(self, context):
        pass

    def create_network_precommit(self, context):
        pass

    def create_network_postcommit(self, context):
        pass

    def create_subnet_precommit(self, context):
        pass

    def create_subnet_postcommit(self, context):
        pass
