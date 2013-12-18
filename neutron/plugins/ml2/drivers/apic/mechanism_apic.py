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
import sqlalchemy as sa
import uuid

from oslo.config import cfg

from neutron.db import api as db_api
from neutron.db import model_base
from neutron.openstack.common import log
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2.drivers.apic import apic_client
from neutron.plugins.ml2.drivers.apic import config

LOG = log.getLogger(__name__)


class NetworkEPG(model_base.BASEV2):
    """EPG's created on the apic per network"""

    __tablename__ = 'ml2_apic_epgs'

    network_id = sa.Column(sa.String(64), nullable=False,
                           primary_key=True)
    epg_id = sa.Column(sa.String(64), nullable=False)
    segmentation_id = sa.Column(sa.String(64), nullable=False)


class Epg(object):
    def __init__(self):
        pass


class Tenant(object):
    def __init__(self):
        pass


class AppProfile(object):
    def __init__(self):
        pass


class APICManager(object):
    def __init__(self):
        # Connect to the the APIC
        host = cfg.CONF.ml2_apic.apic_host
        port = cfg.CONF.ml2_apic.apic_port
        username = cfg.CONF.ml2_apic.apic_username
        password = cfg.CONF.ml2_apic.apic_password
        self.apic = apic_client.RestClient(host, port, username, password)

        # Update lists of managed objects from the APIC
        self.apic_tenants = self.apic.fvTenant.list_all()
        self.apic_bridge_domains = self.apic.fvBD.list_all()
        self.apic_subnets = self.apic.fvSubnet.list_all()
        self.apic_app_profiles = self.apic.fvAp.list_all()
        self.apic_epgs = self.apic.fvAEPg.list_all()
        self.apic_filters = self.apic.vzFilter.list_all()

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
        self.apic_epgs = self.apic.fvAEPg.list_all()

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

    def ensure_epg_created_for_network(self, network_id):
        # Check if an EPG is already present for this network
        session = db_api.get_session()
        epg = session.query(NetworkEPG).filter_by(network_id=network_id).first()
        if epg:
            return epg

        # Create a new EPG on the APIC
        epg_uid = uuid.uuid4()
        self.apic.fvAEPg.create(epg_uid)
    
        epg = NetworkEPG(network_id=network_id,
                         epg_id=epg_uid)
       
        # Get segmentation id 
        
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

    def create_network_postcommit(self, context):
        pass

    def delete_network_precommit(self, context):
        net_id = context.current['id']
        tenant_id = context.current['tenant_id']

        self.apic_manager.delete_bd_on_apic(tenant_id, net_id)

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
