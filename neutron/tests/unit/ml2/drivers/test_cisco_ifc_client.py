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
        #self.addCleanup(mock.patch.stopall)

    def test_cisco_ifc_client_session(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.assertIsNotNone(s.authentication)
        s.logout()
        self.assertIsNone(s.authentication)

    def test_query_top_system(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        top_system, ts_data = s.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        self.assertEqual(top_system.status_code, 200)
        self.assertIsNotNone(top_system)
        self.assertIsNotNone(ts_data)
        self.assertEqual(len(ts_data), 1)
        self.assertIn('topSystem', ts_data[0])
        signed_out = s.logout()
        self.assertTrue(signed_out)
        self.assertIsNone(s.authentication)

    def test_lookup_nonexistant_tenant(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)

    def test_lookup_existing_tenant(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        tenant = s.tenant.get('infra')
        self.assertEqual(tenant[0]['fvTenant']['attributes']['name'], 'infra')

    def test_create_and_lookup_tenant(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.tenant.get(TEST_TENANT)
            s.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_tenant = s.tenant.create(TEST_TENANT)
        self.assertIsNotNone(new_tenant)
        s.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)

    def test_lookup_nonexistant_network(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.assertRaises(cexc.ApicManagedObjectNotFound, s.bridge_domain.get,
                          'LarryKing', 'CableNews')

    def test_create_and_lookup_network(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
            s.bridge_domain.delete(TEST_TENANT, TEST_NETWORK)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            s.tenant.get(TEST_TENANT)
            s.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_network = s.bridge_domain.create(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(new_network)
        tenant = s.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        s.bridge_domain.delete(TEST_TENANT, TEST_NETWORK)
        self.assertRaises(cexc.ApicManagedObjectNotFound, s.bridge_domain.get,
                          TEST_TENANT, TEST_NETWORK)
        s.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)

    def test_create_and_lookup_subnet(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.subnet.get(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
            s.subnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            s.tenant.get(TEST_TENANT)
            s.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_sn = s.subnet.create(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = s.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        s.subnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(cexc.ApicManagedObjectNotFound, s.subnet.get,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        s.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)

    def test_create_bd_with_subnet_and_l3ctx(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        new_sn = s.subnet.create(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = s.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        bd = s.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        sn = s.subnet.get(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(sn)
        # create l3ctx on tenant
        new_l3ctx = s.l3ctx.create(TEST_TENANT, TEST_L3CTX)
        self.assertIsNotNone(new_l3ctx)
        l3c = s.l3ctx.get(TEST_TENANT, TEST_L3CTX)
        self.assertIsNotNone(l3c)
        # assocate l3ctx with BD  # TODO: how?
        # bd = s.bridge_domain.update(TEST_TENANT, TEST_NETWORK, ...)
        s.l3ctx.delete(TEST_TENANT, TEST_NETWORK, TEST_L3CTX)
        # tenant and BD should still exist
        tenant = s.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        bd = s.bridge_domain.get(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(bd)
        s.subnet.delete(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(cexc.ApicManagedObjectNotFound, s.subnet.get,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        s.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)

    def test_list_tenants(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        tlist = s.tenant.list_all()
        self.assertIsNotNone(tlist)

    def test_list_networks(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        nlist = s.bridge_domain.list_all()
        self.assertIsNotNone(nlist)

    def test_list_subnets(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        snlist = s.subnet.list_all()
        self.assertIsNotNone(snlist)

    def test_list_app_profiles(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        aplist = s.app_profile.list_all()
        self.assertIsNotNone(aplist)

    def test_list_epgs(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        elist = s.epg.list_all()
        self.assertIsNotNone(elist)

    def test_create_and_lookup_contract(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        new_contract = s.contract.create(TEST_TENANT, TEST_CONTRACT)
        self.assertIsNotNone(new_contract)
        tenant = s.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        s.contract.delete(TEST_TENANT, TEST_CONTRACT)
        self.assertRaises(cexc.ApicManagedObjectNotFound, s.contract.get,
                          TEST_TENANT, TEST_CONTRACT)
        s.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)

    def test_create_and_lookup_entry(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.entry.get(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
            s.entry.delete(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        except cexc.ApicManagedObjectNotFound:
            pass
        try:
            s.tenant.get(TEST_TENANT)
            s.tenant.delete(TEST_TENANT)
        except cexc.ApicManagedObjectNotFound:
            pass
        new_sn = s.entry.create(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.assertIsNotNone(new_sn)
        tenant = s.tenant.get(TEST_TENANT)
        self.assertIsNotNone(tenant)
        s.entry.update(TEST_TENANT, TEST_FILTER, TEST_ENTRY,
                       prot='udp', dToPort='pop3')
        s.entry.delete(TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        self.assertRaises(cexc.ApicManagedObjectNotFound, s.entry.get,
                          TEST_TENANT, TEST_FILTER, TEST_ENTRY)
        s.tenant.delete(TEST_TENANT)
        self.assertRaises(cexc.ApicManagedObjectNotFound,
                          s.tenant.get, TEST_TENANT)
