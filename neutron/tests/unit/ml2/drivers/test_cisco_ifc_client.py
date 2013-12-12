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

from neutron.common import log
from neutron.plugins.ml2.drivers.cisco import exceptions as cexc
from neutron.plugins.ml2.drivers.vespa import ifc_client as ifc
from neutron.tests import base


LOG = log.logging.getLogger(__name__)
ML2_PLUGIN = 'neutron.plugins.ml2.plugin.Ml2Plugin'
PHYS_NET = 'physnet1'

TEST_HOST = '172.21.32.71'   # was .116, .120, .71
TEST_PORT = '7580'           # was 8000
TEST_USR = 'admin'
TEST_PWD = 'ins3965!'

TEST_TENANT = 'citizen14'
TEST_NETWORK = 'network99'
TEST_SUBNET = '10.3.2.1/24'
TEST_L3CTX = 'bananas'
TEST_AP = 'appProfile001'
TEST_EPG = 'endPointGroup001'

TEST_CONTRACT = 'MySoul'
TEST_SUBJECT = 'ForSale'
TEST_FILTER = 'Carbon'
TEST_ENTRY = 'FrontDoor'


class TestCiscoIfcClient(base.BaseTestCase):

    def setUp(self):
        """
        docstring
        """
        super(TestCiscoIfcClient, self).setUp()
        self.apic = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.addCleanup(self.sign_out)
        #self.addCleanup(mock.patch.stopall)

    def sign_out(self):
        signed_out = self.apic.logout()
        self.assertIsNotNone(signed_out)
        self.assertIsNone(self.apic.authentication)

    def delete_test_objects(self):
        """In case previous test attempts didn't clean up."""
        try:
            self.apic.bridge_domain.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.rsctx.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.ctx.create(TEST_TENANT, TEST_L3CTX)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass

    def test_cisco_ifc_client_session(self):
        self.delete_test_objects()
        self.assertIsNotNone(self.apic.authentication)

    def test_query_top_system(self):
        top_system = self.apic.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        name = top_system[0]['topSystem']['attributes']['name']
        self.assertEqual(name, 'ifc1')

    def test_lookup_nonexistant_tenant(self):
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)

    def test_lookup_existing_tenant(self):
        tenant = self.apic.tenant.get('infra')
        self.assertEqual(tenant[0]['fvTenant']['attributes']['name'], 'infra')

    def test_create_and_lookup_tenant(self):
        try:
            self.apic.tenant.get(TEST_TENANT)
            self.apic.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_tenant = self.apic.tenant.create(TEST_TENANT)
        self.assertIsNotNone(new_tenant)
        self.apic.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)

    def test_lookup_nonexistant_network(self):
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.bridge_domain.get,
                          'LarryKing', 'CableNews')

    def test_create_and_lookup_network(self):
        try:
            self.apic.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
            self.apic.bridge_domain.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.tenant.get(TEST_TENANT)
            self.apic.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_network = self.apic.bridge_domain.create(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(new_network)
        tenant = self.apic.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.bridge_domain.delete(TEST_TENANT, TEST_NETWORK)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.bridge_domain.get,
                          TEST_TENANT, TEST_NETWORK)
        self.apic.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)

    def test_create_and_lookup_subnet(self):
        try:
            self.apic.subnet.get(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
            self.apic.subnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.tenant.get(TEST_TENANT)
            self.apic.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_sn = self.apic.subnet.create(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = self.apic.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.subnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(cexc.ApicManagedObjectNotFound, self.apic.subnet.get,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.apic.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)

    def test_create_bd_with_subnet_and_l3ctx(self):
        self.delete_test_objects()
        new_sn = self.apic.subnet.create(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = self.apic.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        bd = self.apic.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        sn = self.apic.subnet.get(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(sn)
        # create l3ctx on tenant
        new_l3ctx = self.apic.ctx.create(TEST_TENANT, TEST_L3CTX)
        self.assertIsNotNone(new_l3ctx)
        l3c = self.apic.ctx.get(TEST_TENANT, TEST_L3CTX)
        self.assertIsNotNone(l3c)
        # assocate l3ctx with TEST_NETWORK
        new_rsctx = self.apic.rsctx.create(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(new_rsctx)
        rsctx = self.apic.rsctx.update(TEST_TENANT, TEST_NETWORK,
                               tnFvCtxName=TEST_L3CTX)
        self.assertIsNotNone(rsctx)
        bd = self.apic.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        # delete l3ctx
        self.apic.ctx.delete(TEST_TENANT, TEST_L3CTX)
        # tenant and BD should still exist
        tenant = self.apic.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        bd = self.apic.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        self.apic.subnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(cexc.ApicManagedObjectNotFound, self.apic.subnet.get,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.apic.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)

    def test_list_tenants(self):
        tlist = self.apic.tenant.list_all()
        self.assertIsNotNone(tlist)

    def test_list_networks(self):
        nlist = self.apic.bridge_domain.list_all()
        self.assertIsNotNone(nlist)

    def test_list_subnets(self):
        snlist = self.apic.subnet.list_all()
        self.assertIsNotNone(snlist)

    def test_list_app_profiles(self):
        aplist = self.apic.app_profile.list_all()
        self.assertIsNotNone(aplist)

    def test_list_epgs(self):
        elist = self.apic.epg.list_all()
        self.assertIsNotNone(elist)

    def test_create_and_lookup_contract(self):
        new_contract = self.apic.contract.create(TEST_TENANT, TEST_CONTRACT)
        self.assertIsNotNone(new_contract)
        tenant = self.apic.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.contract.delete(TEST_TENANT, TEST_CONTRACT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.contract.get,
                          TEST_TENANT, TEST_CONTRACT)
        self.apic.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)

    def test_create_and_lookup_entry(self):
        try:
            self.apic.entry.get(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
            self.apic.entry.delete(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.tenant.get(TEST_TENANT)
            self.apic.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_sn = self.apic.entry.create(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.assertIsNotNone(new_sn)
        tenant = self.apic.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.entry.update(TEST_TENANT, TEST_FILTER, TEST_ENTRY,
                       prot='udp', dToPort='pop3')
        self.apic.entry.delete(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.assertRaises(cexc.ApicManagedObjectNotFound, self.apic.entry.get,
                          TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.apic.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.tenant.get, TEST_TENANT)
