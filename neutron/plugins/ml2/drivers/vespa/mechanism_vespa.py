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
        # Update list of tenants from the IFC
        self.get_ifc_tenant_list()

    def get_ifc_tenant_list(self):
        """Get a list of all tenants from the IFC."""
        pass

    def _is_tenant_created_on_ifc(self, tenant_id, tenant_name=None):
        """Check if a tenant exists on the IFC.
        
        Check the local tenant cache and create a new tenant 
        if not found
        """
        pass

    def create_tenant_on_ifc(self, tenant_id, tenant_name):
        """Create an Openstack tenant on the IFC."""
        pass

    def get_epg_list_from_ifc(self):
        """Get a list of all EPG's from the IFC"""
        pass


class VespaMechanismDriver(api.MechanismDriver):
    def initialize(self):
        self.ifc_manager = IFCManager()

    def create_port_precommit(self, context):
        # Get tenant details from port context
        tenant_id = port['tenant_id']
        self.ifc_manager._is_tenant_created_on_ifc(tenant_id)

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
