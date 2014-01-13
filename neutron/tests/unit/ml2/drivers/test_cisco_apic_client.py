# Copyright (c) 2013, 2014 Cisco Systems
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

import mock
# import requests  # noqa
from webob import exc as wexc

from neutron.common import log
from neutron.plugins.ml2.drivers.apic import apic_client as apic
from neutron.plugins.ml2.drivers.cisco import exceptions as cexc
from neutron.tests import base


LOG = log.logging.getLogger(__name__)
ML2_PLUGIN = 'neutron.plugins.ml2.plugin.Ml2Plugin'
PHYS_NET = 'physnet1'

APIC0_HOST = '172.21.32.71'   # was .116, .120, .71
APIC0_PORT = '7580'           # was 8000
APIC1_HOST = '172.21.128.43'
APIC2_HOST = '172.21.128.44'
APIC3_HOST = '172.21.128.45'
APIC4_HOST = '172.21.128.10'
APIC_ADMIN = 'admin'
APIC_PWD = 'ins3965!'

MOCK_HOST = 'fake.controller.local'
TEST_PORT = 7580
TEST_USR = 'notadmin'
TEST_PWD = 'topsecret'

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

TEST_VMMP = 'VMware'  # Change to 'OpenStack' when APIC supports it
TEST_DOMAIN = 'MyCloud'
TEST_PDOM = 'SkidRow'

TEST_NODE_PROF = 'red'
TEST_LEAF = 'green'
TEST_LEAF_TYPE = 'range'
TEST_NODE_BLK = 'blue'
TEST_PORT_PROF = 'leftside'
TEST_PORT_SEL = 'front'
TEST_PORT_TYPE = 'range'
TEST_PORT_BLK1 = 'block01'
TEST_PORT_BLK2 = 'block02'
TEST_ACC_PORT_GRP = 'alpha'
TEST_ATT_ENT_PROF = 'gadget'
TEST_VLAN_NAME = 'hydro'
TEST_VLAN_MODE = 'dynamic'
TEST_VLAN_FROM = 'vlan-2900'
TEST_VLAN_TO = 'vlan-2999'


class TestCiscoApicClientMockController(base.BaseTestCase):

    def setUp(self):
        super(TestCiscoApicClientMockController, self).setUp()

        # Mock the operations in requests
        self.mocked_post = mock.patch('requests.Session.post',
                                      autospec=True).start()
        self.mocked_get = mock.patch('requests.Session.get',
                                     autospec=True).start()

        # Mock responses from the server, for both post and get
        self.mock_post_response = mock.MagicMock()
        self.mocked_post.return_value = self.mock_post_response
        self.mock_post_response.status_code = wexc.HTTPOk.code
        self.mock_get_response = mock.MagicMock()
        self.mocked_get.return_value = self.mock_get_response
        self.mock_get_response.status_code = wexc.HTTPOk.code

        # The mocked response (can be updated by test-cases)
        self.mocked_json_response = {'imdata': []}
        self.mock_post_response.json.return_value = self.mocked_json_response
        self.mock_get_response.json.return_value = self.mocked_json_response
        self.mocked_response = self.mocked_json_response['imdata']

        self.apic = apic.RestClient(MOCK_HOST)
        self.addCleanup(mock.patch.stopall)

    def _mock_ok_response(self, mo, **attrs):
        self.mock_get_response.status_code = wexc.HTTPOk.code
        self.mock_post_response.status_code = wexc.HTTPOk.code
        del self.mocked_response[:]
        if attrs is None:
            return
        if not attrs:
            self.mocked_response.append({})
        else:
            self.mocked_response.append({mo: {'attributes': attrs}})

    def _mock_response_append(self, mo, **attrs):
        self.mocked_response.append({mo: {'attributes': attrs}})

    def _mock_error_response(self, status, err_code='', err_text=u''):
        self.mock_get_response.status_code = status
        self.mock_post_response.status_code = status
        del self.mocked_response[:]
        self.mocked_response.append(
            {'error': {'attributes': {'code': err_code, 'text': err_text}}})

    def _mock_authenticate(self):
        self.apic.login(TEST_USR, TEST_PWD)
        self.apic.authentication = 'logged in'

    def test_client_session_login_ok(self):
        self._mock_ok_response('aaaLogin', userName=TEST_USR)
        self.apic = apic.RestClient(MOCK_HOST, TEST_PORT, TEST_USR, TEST_PWD)
        self.assertEqual(
            self.apic.authentication[0]['aaaLogin']['attributes']['userName'],
            TEST_USR)
        self.assertTrue(self.apic.api_base.startswith('http://'))
        self.assertEqual(self.apic.username, TEST_USR)
        self.assertIsNotNone(self.apic.authentication)
        self.apic = apic.RestClient(MOCK_HOST, TEST_PORT, ssl=True)
        self.assertTrue(self.apic.api_base.startswith('https://'))

    def test_client_session_login_fail(self):
        self._mock_error_response(wexc.HTTPError.code,
                                  err_code='599',
                                  err_text=u'Fake error')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.login, TEST_USR, TEST_PWD)

    def test_client_session_logout_ok(self):
        self._mock_ok_response('aaaLogout', userName=TEST_USR)
        self.apic.logout()
        self.assertIsNone(self.apic.authentication)
        # Multiple signouts should not cause an error
        self.apic.logout()
        self.assertIsNone(self.apic.authentication)

    def test_client_session_logout_fail(self):
        self._mock_authenticate()
        self._mock_ok_response('aaaLogout', status='fail')
        self.apic.logout()
        self.assertIsNone(self.apic.authentication)

    def test_query_not_logged_in(self):
        self.apic.authentication = None
        self.assertRaises(cexc.ApicSessionNotLoggedIn,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_query_no_response(self):
        self._mock_authenticate()
        self.mocked_get.return_value = None
        self.assertRaises(cexc.ApicHostNoResponse,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_query_error_response_no_data(self):
        self._mock_authenticate()
        self._mock_error_response(wexc.HTTPError.code)
        del self.mocked_response[:]
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvTenant.get, TEST_TENANT)

    def test_generic_get_data(self):
        self._mock_authenticate()
        self._mock_ok_response('topSystem', name='ifc1')
        top_system = self.apic.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        name = top_system[0]['topSystem']['attributes']['name']
        self.assertEqual(name, 'ifc1')

    def test_lookup_nonexistant_mo(self):
        self._mock_authenticate()
        self.mock_get_response.json.return_value = {}
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))

    def test_lookup_existing_mo(self):
        self._mock_authenticate()
        self._mock_ok_response('fvTenant', name='infra')
        tenant = self.apic.fvTenant.get('infra')
        self.assertEqual(tenant['name'], 'infra')

    def test_list_mos_ok(self):
        self._mock_authenticate()
        self._mock_ok_response('fvTenant', name='t1')
        self._mock_response_append('fvTenant', name='t2')
        tlist = self.apic.fvTenant.list_all()
        self.assertIsNotNone(tlist)
        self.assertEqual(len(tlist), 2)

    def test_list_mo_names_ok(self):
        self._mock_authenticate()
        self._mock_ok_response('fvTenant', name='t1')
        self._mock_response_append('fvTenant', name='t2')
        tnlist = self.apic.fvTenant.list_names()
        self.assertIsNotNone(tnlist)
        self.assertEqual(len(tnlist), 2)
        self.assertIn('t1', tnlist)
        self.assertIn('t2', tnlist)

    def test_list_mos_split_class_fail(self):
        self._mock_authenticate()
        self._mock_ok_response('fvnsEncapBlk', name='Blk1')
        encap_blks = self.apic.fvnsEncapBlk__vlan.list_all()
        self.assertEqual(len(encap_blks), 1)

    def test_delete_mo_ok(self):
        self._mock_authenticate()
        self.assertFalse(self.apic.fvTenant.delete(TEST_TENANT))

    def test_delete_mo_fail(self):
        self._mock_authenticate()
        self._mock_ok_response('fvTenant', status='fail')
        self.assertFalse(self.apic.fvTenant.delete(TEST_TENANT))

    def test_create_mo_ok(self):
        self._mock_authenticate()
        self.apic.fvTenant.create(TEST_TENANT)
        self._mock_ok_response('fvTenant', name=TEST_TENANT)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)

    def test_create_mo_already_exists(self):
        self._mock_authenticate()
        self._mock_error_response(wexc.HTTPBadRequest,
                                  err_code='103',
                                  err_text=u'Fake 103 error')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.vmmProvP.create, TEST_VMMP)

    def test_create_mo_with_prereq(self):
        self._mock_authenticate()
        bd_args = TEST_TENANT, TEST_NETWORK
        self.apic.fvBD.create(*bd_args)
        self._mock_ok_response('fvBD', name=TEST_NETWORK)
        network = self.apic.fvBD.get(*bd_args)
        self.assertEqual(network['name'], TEST_NETWORK)

    def test_create_mo_prereq_exists(self):
        self._mock_authenticate()
        self.apic.vmmDomP.create(TEST_VMMP, TEST_DOMAIN)
        self._mock_ok_response('vmmDomP', name=TEST_DOMAIN)
        dom = self.apic.vmmDomP.get(TEST_VMMP, TEST_DOMAIN)
        self.assertEqual(dom['name'], TEST_DOMAIN)

    def test_create_mo_fails(self):
        self._mock_authenticate()
        bd_args = TEST_TENANT, TEST_NETWORK
        self._mock_error_response(wexc.HTTPBadRequest,
                                  err_code='not103',
                                  err_text=u'Fake not103 error')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvBD.create, *bd_args)

    def test_update_mo(self):
        self._mock_authenticate()
        self.apic.fvTenant.update(TEST_TENANT, more='extra')
        self._mock_ok_response('fvTenant', name=TEST_TENANT, more='extra')
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)
        self.assertEqual(tenant['more'], 'extra')

    def test_attr_fail_empty_list(self):
        self._mock_authenticate()
        self._mock_ok_response(None)
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))

    def test_attr_fail_empty_obj(self):
        self._mock_authenticate()
        self._mock_ok_response({})
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))


# TODO(Henry): this should go in tempest 3rd party, not unit test
class TestCiscoApicClientLiveController(base.BaseTestCase):
    """
    Test against a real APIC.
    """
    def setUp(self):
        super(TestCiscoApicClientLiveController, self).setUp()
        self.apic = apic.RestClient(APIC4_HOST,
                                    usr=APIC_ADMIN, pwd=APIC_PWD)
        self.addCleanup(self.sign_out)

    def sign_out(self):
        self.apic.logout()
        self.assertIsNone(self.apic.authentication)

    def delete_epg_test_objects(self):
        """In case previous test attempts didn't clean up."""
        self.apic.fvCtx.delete(TEST_TENANT, TEST_L3CTX)
        self.apic.fvAEPg.delete(TEST_TENANT, TEST_AP, TEST_EPG)
        self.apic.fvBD.delete(TEST_TENANT, TEST_NETWORK)
        self.apic.fvRsCtx.delete(TEST_TENANT, TEST_NETWORK)
        self.apic.fvCtx.delete(TEST_TENANT, TEST_L3CTX)
        self.apic.fvTenant.delete(TEST_TENANT)

    def delete_dom_test_objects(self):
        """In case previous test attempts didn't clean up."""
        leaf_node_args = TEST_NODE_PROF, TEST_LEAF, TEST_LEAF_TYPE
        node_blk_args = leaf_node_args + (TEST_NODE_BLK,)
        lhps_args = TEST_PORT_PROF, TEST_PORT_SEL, TEST_PORT_TYPE
        vinst_args = TEST_VLAN_NAME, TEST_VLAN_MODE
        eb_args = vinst_args + (TEST_VLAN_FROM, TEST_VLAN_TO)
        epg_args = TEST_TENANT, TEST_AP, TEST_EPG
        dom_args = TEST_VMMP, TEST_DOMAIN
        domain = self.apic.vmmDomP.get(*dom_args)
        dom_dn = domain and domain['dn'] or None
        port_profile = self.apic.infraAccPortP.get(TEST_PORT_PROF)
        pp_dn = port_profile and port_profile['dn'] or None
        self.apic.fvnsEncapBlk__vlan.delete(*eb_args)
        self.apic.fvnsVlanInstP.delete(*vinst_args)
        if dom_dn:
            self.apic.infraRsDomP.delete(TEST_ATT_ENT_PROF, dom_dn)  # Rs
        self.apic.infraAttEntityP.delete(TEST_ATT_ENT_PROF)
        self.apic.infraRsAccBaseGrp.delete(*lhps_args)
        self.apic.infraAccPortGrp.delete(TEST_ACC_PORT_GRP)
        port_block2_args = lhps_args + (TEST_PORT_BLK2,)
        self.apic.infraPortBlk.delete(*port_block2_args)
        port_block1_args = lhps_args + (TEST_PORT_BLK1,)
        self.apic.infraPortBlk.delete(*port_block1_args)
        self.apic.infraHPortS.delete(*lhps_args)
        if pp_dn:
            self.apic.infraRsAccPortP.delete(TEST_NODE_PROF, pp_dn)  # Rs
        self.apic.infraAccPortP.delete(TEST_PORT_PROF)
        self.apic.infraNodeBlk.delete(*node_blk_args)
        self.apic.infraLeafS.delete(*leaf_node_args)
        self.apic.infraNodeP.delete(TEST_NODE_PROF)
        if dom_dn:
            dom_ref_args = epg_args + (dom_dn,)
            self.apic.fvRsDomAtt.delete(*dom_ref_args)  # Rs
        self.apic.vmmDomP.delete(*dom_args)
        self.apic.fvAEPg.delete(*epg_args)
        self.apic.fvTenant.delete(TEST_TENANT)

    def test_cisco_apic_client_session(self):
        self.delete_epg_test_objects()
        self.assertIsNotNone(self.apic.authentication)

    def test_query_top_system(self):
        top_system = self.apic.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        name = top_system[0]['topSystem']['attributes']['name']
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    def test_lookup_nonexistant_tenant(self):
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))

    def test_lookup_existing_tenant(self):
        tenant = self.apic.fvTenant.get('infra')
        self.assertEqual(tenant['name'], 'infra')

    def test_lookup_nonexistant_network(self):
        self.assertIsNone(self.apic.fvBD.get('LarryKing', 'CableNews'))

    def test_create_tenant_network_subnet(self):
        bd_args = TEST_TENANT, TEST_NETWORK
        subnet_args = TEST_TENANT, TEST_NETWORK, TEST_SUBNET
        self.apic.fvSubnet.delete(*subnet_args)
        self.apic.fvBD.delete(*bd_args)
        self.apic.fvTenant.delete(TEST_TENANT)
        # ----
        self.apic.fvSubnet.create(*subnet_args)
        new_sn = self.apic.fvSubnet.get(*subnet_args)
        self.assertEqual(new_sn['ip'], TEST_SUBNET)
        new_network = self.apic.fvBD.get(*bd_args)
        self.assertEqual(new_network['name'], TEST_NETWORK)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)
        # ----
        self.apic.fvSubnet.delete(*subnet_args)
        self.assertIsNone(self.apic.fvSubnet.get(*subnet_args))
        self.apic.fvBD.delete(*bd_args)
        self.assertIsNone(self.apic.fvBD.get(*bd_args))
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))

    def test_create_bd_with_subnet_and_l3ctx(self):
        self.delete_epg_test_objects()
        self.addCleanup(self.delete_epg_test_objects)
        # ----
        bd_args = TEST_TENANT, TEST_NETWORK
        subnet_args = TEST_TENANT, TEST_NETWORK, TEST_SUBNET
        self.apic.fvSubnet.create(*subnet_args)
        new_sn = self.apic.fvSubnet.get(*subnet_args)
        self.assertEqual(new_sn['ip'], TEST_SUBNET)
        bd = self.apic.fvBD.get(*bd_args)
        self.assertEqual(bd['name'], TEST_NETWORK)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)
        # create l3ctx on tenant
        ctx_args = TEST_TENANT, TEST_L3CTX
        self.apic.fvCtx.create(*ctx_args)
        new_l3ctx = self.apic.fvCtx.get(*ctx_args)
        self.assertEqual(new_l3ctx['name'], TEST_L3CTX)
        # assocate l3ctx with TEST_NETWORK
        self.apic.fvRsCtx.create(*bd_args, tnFvCtxName=TEST_L3CTX)
        rsctx = self.apic.fvRsCtx.get(*bd_args)
        self.assertEqual(rsctx['tnFvCtxName'], TEST_L3CTX)
        # ----
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvRsCtx.delete, *bd_args)
        self.apic.fvCtx.delete(*ctx_args)
        self.assertIsNone(self.apic.fvCtx.get(*ctx_args))
        # tenant and BD should still exist
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)
        bd = self.apic.fvBD.get(*bd_args)
        self.assertEqual(bd['name'], TEST_NETWORK)
        # cleanup deletes the rest

    def test_create_epg_with_bd(self):
        self.delete_epg_test_objects()
        self.addCleanup(self.delete_epg_test_objects)
        # ----
        bd_args = TEST_TENANT, TEST_NETWORK
        epg_args = TEST_TENANT, TEST_AP, TEST_EPG
        self.apic.fvBD.create(*bd_args)
        bd = self.apic.fvBD.get(*bd_args)
        self.assertEqual(bd['name'], TEST_NETWORK)
        self.apic.fvAEPg.create(*epg_args)
        epg = self.apic.fvAEPg.get(*epg_args)
        self.assertEqual(epg['name'], TEST_EPG)
        # associate BD with EPG
        self.apic.fvRsBd.create(*epg_args, tnFvBDName=bd['name'])
        rs_bd = self.apic.fvRsBd.get(*epg_args)
        self.assertEqual(rs_bd['tnFvBDName'], bd['name'])

    def test_list_tenants(self):
        tlist = self.apic.fvTenant.list_all()
        self.assertGreater(len(tlist), 0)

    def test_list_networks(self):
        nlist = self.apic.fvBD.list_all()
        self.assertGreater(len(nlist), 0)

    def test_list_subnets(self):
        bd_args = TEST_TENANT, TEST_NETWORK
        subnet_args = TEST_TENANT, TEST_NETWORK, TEST_SUBNET
        self.apic.fvSubnet.create(*subnet_args)
        snlist = self.apic.fvSubnet.list_all()
        self.assertGreater(len(snlist), 0)
        self.apic.fvSubnet.delete(*subnet_args)
        self.apic.fvBD.delete(*bd_args)
        self.apic.fvTenant.delete(TEST_TENANT)

    def test_list_app_profiles(self):
        aplist = self.apic.fvAp.list_all()
        self.assertGreater(len(aplist), 0)

    def test_list_epgs(self):
        elist = self.apic.fvAEPg.list_all()
        self.assertGreater(len(elist), 0)

    def test_create_and_lookup_contract(self):
        self.apic.vzBrCP.create(TEST_TENANT, TEST_CONTRACT)
        new_contract = self.apic.vzBrCP.get(TEST_TENANT, TEST_CONTRACT)
        self.assertEqual(new_contract['name'], TEST_CONTRACT)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)
        self.apic.vzBrCP.delete(TEST_TENANT, TEST_CONTRACT)
        self.assertIsNone(self.apic.vzBrCP.get(TEST_TENANT, TEST_CONTRACT))
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))

    def test_create_and_lookup_entry(self):
        filter_args = TEST_TENANT, TEST_FILTER
        entry_args = TEST_TENANT, TEST_FILTER, TEST_ENTRY
        self.apic.vzEntry.delete(*entry_args)
        self.apic.fvTenant.delete(TEST_TENANT)
        self.apic.vzEntry.create(*entry_args)
        new_entry = self.apic.vzEntry.get(*entry_args)
        self.assertEqual(new_entry['name'], TEST_ENTRY)
        new_filter = self.apic.vzFilter.get(*filter_args)
        self.assertEqual(new_filter['name'], TEST_FILTER)
        tenant = self.apic.fvTenant.get(TEST_TENANT)
        self.assertEqual(tenant['name'], TEST_TENANT)
        self.apic.vzEntry.update(*entry_args, prot='udp', dToPort='pop3')
        self.apic.vzEntry.delete(*entry_args)
        self.assertIsNone(self.apic.vzEntry.get(*entry_args))
        self.apic.vzFilter.delete(*filter_args)
        self.assertIsNone(self.apic.vzFilter.get(*filter_args))
        self.apic.fvTenant.delete(TEST_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(TEST_TENANT))

    def test_create_physical_domain(self):
        # Create a Physical Domain Profile
        self.apic.physDomP.create(TEST_PDOM)
        pdom = self.apic.physDomP.get(TEST_PDOM)
        self.assertEqual(pdom['dn'], "uni/phys-%s" % TEST_PDOM)
        self.apic.physDomP.delete(TEST_PDOM)
        self.assertIsNone(self.apic.physDomP.get(TEST_PDOM))

    def test_create_domain_vlan_node_mappings(self):
        self.delete_dom_test_objects()
        self.addCleanup(self.delete_dom_test_objects)

        # Create a VMM Domain for the cloud
        dom_args = TEST_VMMP, TEST_DOMAIN
        self.apic.vmmDomP.create(*dom_args)
        domain = self.apic.vmmDomP.get(*dom_args)
        self.assertEqual(domain['name'], TEST_DOMAIN)

        # Get the DN of the VMM domain
        dom_dn = domain['dn']
        self.assertEqual(dom_dn, 'uni/vmmp-%s/dom-%s' % dom_args)

        # Associate the domain with an EPG
        epg_args = TEST_TENANT, TEST_AP, TEST_EPG
        dom_ref_args = epg_args + (dom_dn,)
        self.apic.fvRsDomAtt.create(*dom_ref_args)
        dom_ref = self.apic.fvRsDomAtt.get(*dom_ref_args)
        self.assertEqual(dom_ref['tDn'], dom_dn)

        # Create a Node Profile
        self.apic.infraNodeP.create(TEST_NODE_PROF)
        node_profile = self.apic.infraNodeP.get(TEST_NODE_PROF)
        self.assertEqual(node_profile['name'], TEST_NODE_PROF)

        # Add a Leaf Node Selector to the Node Profile
        leaf_node_args = TEST_NODE_PROF, TEST_LEAF, TEST_LEAF_TYPE
        self.apic.infraLeafS.create(*leaf_node_args)
        leaf_node = self.apic.infraLeafS.get(*leaf_node_args)
        self.assertEqual(leaf_node['name'], TEST_LEAF)

        # Add a Node Block to the Leaf Node Selector
        node_blk_args = leaf_node_args + (TEST_NODE_BLK,)
        self.apic.infraNodeBlk.create(*node_blk_args, from_='13', to_='13')
        node_block = self.apic.infraNodeBlk.get(*node_blk_args)
        self.assertEqual(node_block['name'], TEST_NODE_BLK)

        # Create a Port Profile and get its DN
        self.apic.infraAccPortP.create(TEST_PORT_PROF)
        port_profile = self.apic.infraAccPortP.get(TEST_PORT_PROF)
        pp_dn = port_profile['dn']
        self.assertEqual(pp_dn, 'uni/infra/accportprof-%s' % TEST_PORT_PROF)

        # Associate the Port Profile with the Node Profile
        self.apic.infraRsAccPortP.create(TEST_NODE_PROF, pp_dn)
        ppref = self.apic.infraRsAccPortP.get(TEST_NODE_PROF, pp_dn)
        self.assertEqual(ppref['tDn'], pp_dn)

        # Add a Leaf Host Port Selector to the Port Profile
        lhps_args = TEST_PORT_PROF, TEST_PORT_SEL, TEST_PORT_TYPE
        self.apic.infraHPortS.create(*lhps_args)
        lhps = self.apic.infraHPortS.get(*lhps_args)
        self.assertEqual(lhps['name'], TEST_PORT_SEL)

        # Add a Port Block to the Leaf Host Port Selector
        port_block1_args = lhps_args + (TEST_PORT_BLK1,)
        self.apic.infraPortBlk.create(
            *port_block1_args,
            fromCard='1', toCard='1', fromPort='10', toPort='12')
        port_block1 = self.apic.infraPortBlk.get(*port_block1_args)
        self.assertEqual(port_block1['name'], TEST_PORT_BLK1)

        # Add another Port Block to the Leaf Host Port Selector
        port_block2_args = lhps_args + (TEST_PORT_BLK2,)
        self.apic.infraPortBlk.create(
            *port_block2_args,
            fromCard='1', toCard='1', fromPort='20', toPort='22')
        port_block2 = self.apic.infraPortBlk.get(*port_block2_args)
        self.assertEqual(port_block2['name'], TEST_PORT_BLK2)

        # Create an Access Port Group and get its DN
        self.apic.infraAccPortGrp.create(TEST_ACC_PORT_GRP)
        access_pg = self.apic.infraAccPortGrp.get(TEST_ACC_PORT_GRP)
        self.assertTrue(access_pg)
        apg_dn = access_pg['dn']
        self.assertEqual(apg_dn, 'uni/infra/funcprof/accportgrp-%s' %
                                 TEST_ACC_PORT_GRP)

        # Associate the Access Port Group with Leaf Host Port Selector
        self.apic.infraRsAccBaseGrp.create(*lhps_args, tDn=apg_dn)
        apg_ref = self.apic.infraRsAccBaseGrp.get(*lhps_args)
        self.assertEqual(apg_ref['tDn'], apg_dn)

        # Create an Attached Entity Profile
        self.apic.infraAttEntityP.create(TEST_ATT_ENT_PROF)
        ae_profile = self.apic.infraAttEntityP.get(TEST_ATT_ENT_PROF)
        aep_dn = ae_profile['dn']
        self.assertEqual(aep_dn, 'uni/infra/attentp-%s' % TEST_ATT_ENT_PROF)

        # Associate the cloud domain with the Attached Entity Profile
        self.apic.infraRsDomP.create(TEST_ATT_ENT_PROF, dom_dn)
        dom_ref = self.apic.infraRsDomP.get(TEST_ATT_ENT_PROF, dom_dn)
        self.assertEqual(dom_ref['tDn'], dom_dn)

        # Associate the aep with the apg
        self.apic.infraRsAttEntP.create(TEST_ACC_PORT_GRP, tDn=aep_dn)
        aep_ref = self.apic.infraRsAttEntP.get(TEST_ACC_PORT_GRP)
        self.assertEqual(aep_ref['tDn'], aep_dn)

        # Create a Vlan Instance Profile
        vinst_args = TEST_VLAN_NAME, TEST_VLAN_MODE
        self.apic.fvnsVlanInstP.create(*vinst_args)
        vlan_instp = self.apic.fvnsVlanInstP.get(*vinst_args)
        self.assertEqual(vlan_instp['name'], TEST_VLAN_NAME)

        # Create an Encap Block for the Vlan Instance Profile
        eb_args = vinst_args + (TEST_VLAN_FROM, TEST_VLAN_TO)
        eb_data = {'name': 'encap',
                   'from': TEST_VLAN_FROM, 'to': TEST_VLAN_TO}
        self.apic.fvnsEncapBlk__vlan.create(*eb_args, **eb_data)
        encap_blk = self.apic.fvnsEncapBlk__vlan.get(*eb_args)
        self.assertEqual(encap_blk['name'], 'encap')
        self.assertEqual(encap_blk['from'], TEST_VLAN_FROM)
        self.assertEqual(encap_blk['to'], TEST_VLAN_TO)

        encap_blk = self.apic.fvnsEncapBlk__vlan.list_all()
        self.assertGreater(len(encap_blk), 0)

        # Associate a Vlan Name Space with a Domain
        vlanns = vlan_instp['dn']
        self.apic.infraRsVlanNs.create(*dom_args, tDn=vlanns)
        vlanns_ref = self.apic.infraRsVlanNs.get(*dom_args)
        self.assertEqual(vlanns_ref['tDn'], vlanns)

        # Check if the vmm:EpPD is created
        eppd_args = dom_args + (dom_dn,)
        eppd = self.apic.vmmEpPD.get(*eppd_args)
        self.assertIsNone(eppd)  # TODO: fix
        #self.assertTrue(eppd)
        #eppd_dn = eppd['dn']
        #print eppd_dn
