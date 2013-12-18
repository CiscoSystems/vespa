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
from neutron.plugins.ml2.drivers.apic import apic_client as apic
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


class TestCiscoApicClient(base.BaseTestCase):

    def setUp(self):
        """
        docstring
        """
        super(TestCiscoApicClient, self).setUp()
        self.apic = apic.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.addCleanup(self.sign_out)
        #self.addCleanup(mock.patch.stopall)

    def sign_out(self):
        signed_out = self.apic.logout()
        self.assertIsNotNone(signed_out)
        self.assertIsNone(self.apic.authentication)

    def delete_test_objects(self):
        """In case previous test attempts didn't clean up."""
        try:
            self.apic.fvBD.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.fvRsCtx.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.fvCtx.create(TEST_TENANT, TEST_L3CTX)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.fvTenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass

    def test_cisco_apic_client_session(self):
        self.delete_test_objects()
        self.assertIsNotNone(self.apic.authentication)

    def test_query_top_system(self):
        top_system = self.apic.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        name = top_system[0]['topSystem']['attributes']['name']
        self.assertEqual(name, 'ifc1')

    def test_lookup_nonexistant_tenant(self):
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_lookup_existing_tenant(self):
        tenant = self.apic.fvTenant.get('infra')
        self.assertEqual(tenant[0]['fvTenant']['attributes']['name'], 'infra')

    def test_create_and_lookup_tenant(self):
        try:
            self.apic.fvTenant.get(TEST_TENANT)
            self.apic.fvTenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_tenant = self.apic.fvTenant.create(TEST_TENANT)
        self.assertIsNotNone(new_tenant)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_lookup_nonexistant_network(self):
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvBD.get,
                          'LarryKing', 'CableNews')

    def test_create_and_lookup_network(self):
        try:
            self.apic.fvBD.get(TEST_TENANT, TEST_NETWORK)
            self.apic.fvBD.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.fvTenant.get(TEST_TENANT)
            self.apic.fvTenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_network = self.apic.fvBD.create(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(new_network)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.fvBD.delete(TEST_TENANT, TEST_NETWORK)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvBD.get,
                          TEST_TENANT, TEST_NETWORK)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_create_and_lookup_subnet(self):
        try:
            self.apic.fvSubnet.get(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
            self.apic.fvSubnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.fvTenant.get(TEST_TENANT)
            self.apic.fvTenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_sn = self.apic.fvSubnet.create(TEST_TENANT, TEST_NETWORK,
                                           TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.fvSubnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvSubnet.get,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_create_bd_with_subnet_and_l3ctx(self):
        self.delete_test_objects()
        new_sn = self.apic.fvSubnet.create(TEST_TENANT, TEST_NETWORK,
                                           TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        bd = self.apic.fvBD.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        sn = self.apic.fvSubnet.get(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(sn)
        # create l3ctx on tenant
        new_l3ctx = self.apic.fvCtx.create(TEST_TENANT, TEST_L3CTX)
        self.assertIsNotNone(new_l3ctx)
        l3c = self.apic.fvCtx.get(TEST_TENANT, TEST_L3CTX)
        self.assertIsNotNone(l3c)
        # assocate l3ctx with TEST_NETWORK
        new_rsctx = self.apic.fvRsCtx.create(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(new_rsctx)
        rsctx = self.apic.fvRsCtx.update(TEST_TENANT, TEST_NETWORK,
                               tnFvCtxName=TEST_L3CTX)
        self.assertIsNotNone(rsctx)
        bd = self.apic.fvBD.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        # delete l3ctx
        self.apic.fvCtx.delete(TEST_TENANT, TEST_L3CTX)
        # tenant and BD should still exist
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        bd = self.apic.fvBD.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        self.apic.fvSubnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvSubnet.get,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_list_tenants(self):
        tlist = self.apic.fvTenant.list_all()
        self.assertIsNotNone(tlist)

    def test_list_networks(self):
        nlist = self.apic.fvBD.list_all()
        self.assertIsNotNone(nlist)

    def test_list_subnets(self):
        snlist = self.apic.fvSubnet.list_all()
        self.assertIsNotNone(snlist)

    def test_list_app_profiles(self):
        aplist = self.apic.fvAp.list_all()
        self.assertIsNotNone(aplist)

    def test_list_epgs(self):
        elist = self.apic.fvAEPg.list_all()
        self.assertIsNotNone(elist)

    def test_create_and_lookup_contract(self):
        new_contract = self.apic.vzBrCP.create(TEST_TENANT, TEST_CONTRACT)
        self.assertIsNotNone(new_contract)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.vzBrCP.delete(TEST_TENANT, TEST_CONTRACT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.vzBrCP.get,
                          TEST_TENANT, TEST_CONTRACT)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_create_and_lookup_entry(self):
        try:
            self.apic.vzEntry.get(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
            self.apic.vzEntry.delete(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            self.apic.fvTenant.get(TEST_TENANT)
            self.apic.fvTenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_sn = self.apic.vzEntry.create(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.assertIsNotNone(new_sn)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        self.apic.vzEntry.update(TEST_TENANT, TEST_FILTER, TEST_ENTRY,
                       prot='udp', dToPort='pop3')
        self.apic.vzEntry.delete(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.assertRaises(cexc.ApicManagedObjectNotFound, self.apic.vzEntry.get,
                          TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          self.apic.fvTenant.get, TEST_TENANT)
