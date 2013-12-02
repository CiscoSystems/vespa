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
TEST_SUBNET = '10.3.2.1'
#TEST_SUBNET = 'sub10321'
TEST_AP = 'appProfile001'
TEST_EPG = 'endPointGroup001'


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
        top_system, ts_data = s.get('class/topSystem')
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
        self.assertRaises(ValueError, s.get_tenant, TEST_TENANT)

    def test_lookup_existing_tenant(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        tenant = s.get_tenant('infra')
        self.assertEqual(tenant[0]['fvTenant']['attributes']['name'], 'infra')

    def test_create_and_lookup_tenant(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.get_tenant(TEST_TENANT)
            s.delete_tenant(TEST_TENANT)
        except ValueError:
            pass
        new_tenant = s.create_tenant(TEST_TENANT)
        self.assertIsNotNone(new_tenant)
        s.delete_tenant(TEST_TENANT)
        self.assertRaises(ValueError, s.get_tenant, TEST_TENANT)

    def test_lookup_nonexistant_network(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.assertRaises(ValueError, s.get_bridge_domain,
                          'LarryKing', 'CableNews')

    def test_create_and_lookup_network(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.get_bridge_domain(TEST_TENANT, TEST_NETWORK)
            s.delete_bridge_domain(TEST_TENANT, TEST_NETWORK)
        except ValueError:
            pass
        try:
            s.get_tenant(TEST_TENANT)
            s.delete_tenant(TEST_TENANT)
        except ValueError:
            pass
        new_network = s.create_bridge_domain(TEST_TENANT, TEST_NETWORK)
        self.assertIsNotNone(new_network)
        tenant = s.get_tenant(TEST_TENANT)
        self.assertIsNotNone(tenant)
        s.delete_bridge_domain(TEST_TENANT, TEST_NETWORK)
        self.assertRaises(ValueError, s.get_bridge_domain,
                          TEST_TENANT, TEST_NETWORK)
        s.delete_tenant(TEST_TENANT)
        self.assertRaises(ValueError, s.get_tenant, TEST_TENANT)

    def test_create_and_lookup_subnet(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        try:
            s.get_subnet(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
            s.delete_subnet(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        except ValueError:
            pass
        try:
            s.get_tenant(TEST_TENANT)
            s.delete_tenant(TEST_TENANT)
        except ValueError:
            pass
        new_sn = s.create_subnet(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertIsNotNone(new_sn)
        tenant = s.get_tenant(TEST_TENANT)
        self.assertIsNotNone(tenant)
        s.delete_subnet(TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        self.assertRaises(ValueError, s.get_subnet,
                          TEST_TENANT, TEST_NETWORK, TEST_SUBNET)
        s.delete_tenant(TEST_TENANT)
        self.assertRaises(ValueError, s.get_tenant, TEST_TENANT)

    def test_list_tenants(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        tlist = s.list_tenants()
        self.assertIsNotNone(tlist)

    def test_list_networks(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        nlist = s.list_bridge_domains()
        self.assertIsNotNone(nlist)

    def test_list_subnets(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        snlist = s.list_subnets()
        self.assertIsNotNone(snlist)

    def test_list_app_profiles(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        aplist = s.list_app_profiles()
        self.assertIsNotNone(aplist)

    def test_list_epgs(self):
        s = ifc.RestClient(TEST_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        elist = s.list_epgs()
        self.assertIsNotNone(elist)
