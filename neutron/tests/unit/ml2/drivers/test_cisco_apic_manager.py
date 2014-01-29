# Copyright (c) 2014 Cisco Systems
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

from neutron.common import log
from neutron.plugins.ml2.drivers.apic import apic_manager
from neutron.tests import base
from neutron.tests.unit.ml2.drivers import test_cisco_apic_common as mocked


LOG = log.logging.getLogger(__name__)


class TestCiscoApicManager(base.BaseTestCase,
                           mocked.ControllerMixin,
                           mocked.ConfigMixin):

    def setUp(self):
        super(TestCiscoApicManager, self).setUp()
        mocked.ControllerMixin.set_up_mocks(self)
        mocked.ConfigMixin._set_up_mocks(self)

        self.db_session = mock.patch('neutron.db.api.get_session').start()

        # Tests are based on authenticated session, so log in here
        self.mock_ok_post_response('aaaLogin', userName=mocked.APIC_USR,
                                   token='ok', refreshTimeoutSeconds=300)
        # After login, the manager gets lists of objects ...
        mos = ['fvTenant', 'fvBD', 'fvSubnet', 'fvAp', 'fvAEPg', 'vzFilter']
        for mo in mos:
            name1 = mo[2:].lower() + '1'
            name2 = name1[:-1] + '2'
            self.mock_ok_get_response(mo, name=name1)
            self.mock_append_to_get(mo, name=name2)

        self.mgr = apic_manager.APICManager()
        self.reset_reponses()

        self.addCleanup(mock.patch.stopall)

    def mock_db_query_filterby_first_return(self, value):
        """Mock db.session.query().filterby().first() to return value."""
        query = self.db_session.return_value.query.return_value
        query.filter_by.return_value.first.return_value = value

    def test_mgr_session_login(self):
        login = self.mgr.apic.authentication
        self.assertEqual(login['userName'], mocked.APIC_USR)

    def test_mgr_session_logout(self):
        self.mock_ok_post_response('aaaLogout', userName=mocked.APIC_USR)
        self.mgr.apic.logout()
        self.assertIsNone(self.mgr.apic.authentication)

    def test_to_range(self):
        port_list = [4, 2, 3, 1, 7, 8, 10, 20, 6, 22, 21]
        expected_ranges = [(1, 4), (6, 8), (10, 10), (20, 22)]
        port_ranges = [r for r in self.mgr._to_range(port_list)]
        self.assertEqual(port_ranges, expected_ranges)

    def test_get_profiles(self):
        self.mock_db_query_filterby_first_return('faked')
        self.assertEqual(self.mgr.get_port_profile_for_node(
            'node'), 'faked')
        self.assertEqual(self.mgr.get_profile_for_module(
            'node', 'prof', 'module'), 'faked')
        self.assertEqual(self.mgr.get_profile_for_module_and_ports(
            'node', 'prof', 'module', 'from', 'to'), 'faked')

    def test_add_profile(self):
        session = mock.Mock()
        session.add = mock.Mock()
        session.flush = mock.Mock()
        self.db_session.return_value = session
        self.mgr.add_profile_for_module_and_ports(
            'node', 'prof', 'hpselc', 'module', 'from', 'to')
        self.assertTrue(session.add.called)
        self.assertTrue(session.flush.called)

    def test_ensure_port_profile_created(self):
        port_name = mocked.APIC_PORT
        self.mock_ok_post_response('infraAccPortP', name=port_name)
        self.mock_ok_get_response('infraAccPortP', name=port_name)
        port = self.mgr.ensure_port_profile_created_on_apic(port_name)
        self.assertEqual(port['name'], port_name)

    def test_ensure_node_profile_created_for_switch_old(self):
        old_switch = mocked.APIC_NODE_PROF
        self.mock_ok_post_response('infraNodeP', name=old_switch)
        self.mock_ok_get_response('infraNodeP', name=old_switch)
        self.mgr.ensure_node_profile_created_for_switch(old_switch)
        old_name = self.mgr.node_profiles[old_switch]['object']['name']
        self.assertEqual(old_name, old_switch)

    def test_ensure_node_profile_created_for_switch_new(self):
        new_switch = mocked.APIC_NODE_PROF
        # delete node prof   TODO(Henry): why is this done first?
        self.mock_ok_post_response('infraNodeP', name=new_switch)
        self.mock_ok_get_response('infraNodeP')
        self.mock_responses_for_create('infraNodeP')
        self.mock_responses_for_create('infraLeafS')
        self.mock_responses_for_create('infraNodeBlk')
        self.mock_ok_get_response('infraNodeP', name=new_switch)
        self.mgr.ensure_node_profile_created_for_switch(new_switch)
        new_name = self.mgr.node_profiles[new_switch]['object']['name']
        self.assertEqual(new_name, new_switch)

    def test_ensure_vmm_domain_created_old(self):
        dom = mocked.APIC_DOMAIN
        self.mock_ok_get_response('vmmDomP', name=dom)
        self.mgr.ensure_vmm_domain_created_on_apic(dom)
        old_dom = self.mgr.vmm_domain['name']
        self.assertEqual(old_dom, mocked.APIC_DOMAIN)

    def _mock_new_dom_responses(self, dom):
        vmm = mocked.APIC_VMMP
        dn = self.mgr.apic.vmmDomP.mo.dn(vmm, dom)
        self.mock_ok_get_response('vmmDomP')
        self.mock_responses_for_create('vmmDomP')
        self.mock_ok_get_response('vmmDomP', name=dom, dn=dn)

    def test_ensure_vmm_domain_created_new_no_vlan_ns(self):
        dom = mocked.APIC_DOMAIN
        self._mock_new_dom_responses(dom)
        self.mgr.ensure_vmm_domain_created_on_apic(dom)
        new_dom = self.mgr.vmm_domain['name']
        self.assertEqual(new_dom, mocked.APIC_DOMAIN)

    def _mock_new_vlan_ns_responses(self, ns_dn):
        self.mock_responses_for_create('vmmDomP')
        self.mock_ok_post_response('infraRsVlanNs', tDn=ns_dn)

    def test_ensure_vmm_domain_created_new_with_vlan_ns(self):
        dom = mocked.APIC_DOMAIN
        self._mock_new_dom_responses(dom)
        ns = {'dn': 'test_vlan_ns'}
        self._mock_new_vlan_ns_responses(ns['dn'])
        self.mgr.ensure_vmm_domain_created_on_apic(dom, vlan_ns=ns)
        new_dom = self.mgr.vmm_domain['name']
        self.assertEqual(new_dom, mocked.APIC_DOMAIN)

    def test_ensure_vmm_domain_created_new_with_vxlan_ns(self):
        dom = mocked.APIC_DOMAIN
        self._mock_new_dom_responses(dom)
        ns = {'dn': 'test_vxlan_ns'}
        self._mock_new_vlan_ns_responses(ns['dn'])
        self.mgr.ensure_vmm_domain_created_on_apic(dom, vxlan_ns=ns)
        new_dom = self.mgr.vmm_domain['name']
        self.assertEqual(new_dom, mocked.APIC_DOMAIN)

    def test_ensure_infra_created_no_infra(self):
        self.mgr.switch_dict = {}
        self.mgr.ensure_infra_created_on_apic()

    def test_ensure_infra_created_seq1(self):
        self.mgr.ensure_node_profile_created_for_switch = mock.Mock()  # 119
        self.mgr.get_port_profile_for_node = mock.Mock(
            return_value=None)                                         # 123
        self.mgr.ensure_port_profile_created_on_apic = mock.Mock(
            return_value={'dn': 'port_profile_dn'})                    # 127

        def _profile_for_module(switch, ppn, module):
            profile = mock.MagicMock()
            profile.hpselc_id = '-'.join([switch, module, 'hpselc_id'])
            return profile

        self.mgr.get_profile_for_module = mock.MagicMock(
            side_effect=_profile_for_module)                      # 146, 155
        self.mgr.get_profile_for_module_and_ports = mock.Mock(
            return_value=None)                                         # 161
        self.mgr.add_profile_for_module_and_ports = mock.Mock()        # 171

        num_switches = len(self.mgr.switch_dict)
        for loop in range(num_switches):
            self.mock_responses_for_create('infraRsAccPortP')          # 130
            self.mock_responses_for_create('infraPortBlk')             # 165

        self.mgr.ensure_infra_created_on_apic()
        # Just coverage, nothing to verify.
        # TODO(Henry): verify something

    def test_ensure_infra_created_seq2(self):
        self.mgr.ensure_node_profile_created_for_switch = mock.Mock()  # 119

        def _profile_for_node(switch):
            profile = mock.MagicMock()
            profile.profile_id = '-'.join([switch, 'profile_id'])
            return profile

        self.mgr.get_port_profile_for_node = mock.MagicMock(
            side_effect=_profile_for_node)                        # 123, 132
        self.mgr.get_profile_for_module = mock.Mock(
            return_value=None)                                         # 146
        self.mgr.function_profile = {'dn': 'dn'}                       # 151
        self.mgr.get_profile_for_module_and_ports = mock.Mock(
            return_value=True)                                         # 161

        num_switches = len(self.mgr.switch_dict)
        for loop in range(num_switches):
            self.mock_responses_for_create('infraRsAccPortP')          # 130
            self.mock_responses_for_create('infraHPortS')              # 149
            self.mock_responses_for_create('infraRsAccBaseGrp')        # 152

        self.mgr.ensure_infra_created_on_apic()
        # Just coverage, nothing to verify.
        # TODO(Henry): verify something

    def _mock_vmm_dom_prereq(self, dom):
        self._mock_new_dom_responses(dom)
        self.mgr.ensure_vmm_domain_created_on_apic(dom)

    def test_ensure_entity_profile_created_old(self):
        ep = mocked.APIC_ATT_ENT_PROF
        self.mock_ok_get_response('infraAttEntityP', name=ep)
        self.mgr.ensure_entity_profile_created_on_apic(ep)

    def _mock_new_entity_profile(self):
        self.mock_ok_get_response('infraAttEntityP')
        self.mock_responses_for_create('infraAttEntityP')
        self.mock_responses_for_create('infraRsDomP')
        self.mock_ok_get_response('infraAttEntityP')

    def test_ensure_entity_profile_created_new(self):
        self._mock_vmm_dom_prereq(mocked.APIC_DOMAIN)
        ep = mocked.APIC_ATT_ENT_PROF
        self._mock_new_entity_profile()
        self.mgr.ensure_entity_profile_created_on_apic(ep)

    def _mock_entity_profile_preqreq(self):
        self._mock_vmm_dom_prereq(mocked.APIC_DOMAIN)
        ep = mocked.APIC_ATT_ENT_PROF
        self._mock_new_entity_profile()
        self.mgr.ensure_entity_profile_created_on_apic(ep)

    def test_ensure_function_profile_created_old(self):
        self._mock_entity_profile_preqreq()
        fp = mocked.APIC_FUNC_PROF
        self.mock_ok_get_response('infraAccPortGrp', name=fp)
        self.mgr.ensure_function_profile_created_on_apic(fp)
        old_fp = self.mgr.function_profile['name']
        self.assertEqual(old_fp, fp)

    def _mock_new_function_profile(self, fp):
        dn = self.mgr.apic.infraAttEntityP.mo.dn(fp)
        self.mock_responses_for_create('infraAccPortGrp')
        self.mock_responses_for_create('infraRsAttEntP')
        self.mock_ok_get_response('infraAccPortGrp', name=fp, dn=dn)

    def test_ensure_function_profile_created_new(self):
        self.reset_reponses()
        fp = mocked.APIC_FUNC_PROF
        dn = self.mgr.apic.infraAttEntityP.mo.dn(fp)
        self.mgr.entity_profile = {'dn': dn}
        self.mock_ok_get_response('infraAccPortGrp')
        self.mock_responses_for_create('infraAccPortGrp')
        self.mock_responses_for_create('infraRsAttEntP')
        self.mock_ok_get_response('infraAccPortGrp', name=fp, dn=dn)
        self.mgr.ensure_function_profile_created_on_apic(fp)
        new_fp = self.mgr.function_profile['name']
        self.assertEqual(new_fp, fp)

    def test_ensure_vlan_ns_created_old(self):
        ns = mocked.APIC_VLAN_NAME
        mode = mocked.APIC_VLAN_MODE
        self.mock_ok_get_response('fvnsVlanInstP', name=ns, mode=mode)
        old_ns = self.mgr.ensure_vlan_ns_created_on_apic(ns, '100', '199')
        self.assertEqual(old_ns['name'], ns)

    def _mock_new_vlan_instance(self, ns, vlan_encap=None):
        self.mock_ok_post_response('infra')
        self.mock_ok_post_response('fvnsVlanInstP')
        if vlan_encap:
            self.mock_ok_get_response('fvnsEncapBlk', **vlan_encap)
        else:
            self.mock_ok_get_response('fvnsEncapBlk')
            self.mock_ok_post_response('infra')
            self.mock_ok_post_response('fvnsVlanInstP')
            self.mock_ok_post_response('fvnsEncapBlk')
        self.mock_ok_get_response('fvnsVlanInstP', name=ns)

    def test_ensure_vlan_ns_created_new_no_encap(self):
        ns = mocked.APIC_VLAN_NAME
        self.mock_ok_get_response('fvnsVlanInstP')
        self._mock_new_vlan_instance(ns)
        new_ns = self.mgr.ensure_vlan_ns_created_on_apic(ns, '200', '299')
        self.assertEqual(new_ns['name'], ns)

    def test_ensure_vlan_ns_created_new_with_encap(self):
        ns = mocked.APIC_VLAN_NAME
        self.mock_ok_get_response('fvnsVlanInstP')
        ns_args = {'name': 'encap', 'from': '300', 'to': '399'}
        self._mock_new_vlan_instance(ns, vlan_encap=ns_args)
        new_ns = self.mgr.ensure_vlan_ns_created_on_apic(ns, '300', '399')
        self.assertEqual(new_ns['name'], ns)

    def test_ensure_tenant_created_on_apic(self):
        self.mgr.apic_tenants = ['one', 'two', 'three']
        self.mgr.ensure_tenant_created_on_apic('two')
        self.mock_ok_post_response('fvTenant', name='four')
        self.mgr.ensure_tenant_created_on_apic('four')
        self.assertEqual(self.mgr.apic_tenants,
                         ['one', 'two', 'three', 'four'])

    def test_ensure_bd_created(self):
        self.mgr.apic_bridge_domains = ['one', 'two', 'three']
        self.mgr.ensure_bd_created_on_apic('t1', 'two')
        self.mock_ok_post_response('fvTenant', name='t2')
        self.mock_ok_post_response('fvBD', name='four')
        self.mock_ok_post_response('fvTenant', name='t2')
        self.mock_ok_post_response('fvBD', name='four')
        self.mock_ok_post_response('fvRsCtx', name='ctx')
        self.mgr.ensure_bd_created_on_apic('t2', 'four')
        self.assertEqual(self.mgr.apic_bridge_domains,
                         ['one', 'two', 'three', 'four'])

    def test_delete_bd(self):
        self.mock_ok_post_response('fvBD')
        self.mgr.delete_bd_on_apic('t1', 'bd')
        # Just coverage, nothing to verify.
        # TODO(Henry): should mgr.apic_bridge_domains be updated?

    def test_ensure_subnet_created(self):
        self.mgr.apic_subnets = ['one', 'two', 'three']
        self.mgr.ensure_subnet_created_on_apic('t0', 'bd1', 'two', '2.2.2.2')
        self.mock_ok_post_response('fvTenant', name='t2')
        self.mock_ok_post_response('fvBD', name='bd3')
        self.mock_ok_post_response('fvSubnet', name='four')
        self.mgr.ensure_subnet_created_on_apic('t2', 'bd3', 'four', '4.4.4.4')
        self.assertEqual(self.mgr.apic_subnets,
                         ['one', 'two', 'three', 'four'])

    def test_ensure_filter_created(self):
        self.mgr.apic_filters = ['one', 'two', 'three']
        self.mgr.ensure_filter_created_on_apic('t1', 'two')
        self.mock_ok_post_response('fvTenant', name='t2')
        self.mock_ok_post_response('vzFilter', name='four')
        self.mgr.ensure_filter_created_on_apic('t2', 'four')
        self.assertEqual(self.mgr.apic_filters,
                         ['one', 'two', 'three', 'four'])

    def test_get_epg_list(self):
        self.mock_ok_get_response('fvAEPg', name='one')
        self.mock_append_to_get('fvAEPg', name='two')
        self.mgr.get_epg_list_from_apic()
        self.assertEqual(self.mgr.apic_epgs, ['one', 'two'])

    def test_ensure_epg_created_for_network_old(self):
        self.mock_db_query_filterby_first_return('faked')
        epg = self.mgr.ensure_epg_created_for_network('X', 'Y')
        self.assertEqual(epg, 'faked')

    def test_ensure_epg_created_for_network_new(self):
        tenant = mocked.APIC_TENANT
        network = mocked.APIC_NETWORK
        epg = mocked.APIC_EPG
        dom = mocked.APIC_DOMAIN
        session = mock.Mock()
        session.add = mock.Mock()
        session.flush = mock.Mock()
        query = session.query.return_value
        query.filter_by.return_value.first.return_value = None
        self.db_session.return_value = session
        self.mock_responses_for_create('fvAEPg')
        self.mock_ok_get_response('fvBD', name=network)
        self.mock_responses_for_create('fvRsBd')
        self.mock_ok_get_response('vmmDomP', name=dom, dn='dn')
        self.mock_responses_for_create('fvRsDomAtt')
        self.mock_ok_get_response('fvAEPg', name=epg)
        new_epg = self.mgr.ensure_epg_created_for_network(tenant, network)
        self.assertEqual(new_epg.network_id, network)
        self.assertTrue(session.add.called)
        self.assertTrue(session.flush.called)

    def test_delete_epg_for_network_no_epg(self):
        self.mock_db_query_filterby_first_return(None)
        self.mgr.delete_epg_for_network('tenant', 'network')
        # Just coverage, nothing to verify
        # TODO(Henry): should mgr.apic_epgs be not updated?

    def test_delete_epg_for_network(self):
        epg_id = 'epg01'
        epg = mock.Mock()
        epg.epg_id = epg_id
        session = mock.Mock()
        session.delete = mock.Mock()
        session.flush = mock.Mock()
        query = session.query.return_value
        query.filter_by.return_value.first.return_value = epg
        self.db_session.return_value = session
        self.mock_ok_post_response('fvAEPg', name=epg_id)
        self.mgr.delete_epg_for_network('tenant', 'network')
        self.assertTrue(session.delete.called)
        self.assertTrue(session.flush.called)

    def test_ensure_path_created_for_port(self):
        epg = mock.Mock()
        epg.epg_id = 'epg01'
        eepg = mock.MagicMock(return_value=epg)
        apic_manager.APICManager.ensure_epg_created_for_network = eepg
        self.mock_ok_get_response('fvRsPathAtt', tDn='foo')
        self.mgr.ensure_path_created_for_port('tenant', 'network', 'ubuntu2',
                                              'static')
        # TODO(Henry): the above breaks for an unknown host
        # Just coverage, nothing to verify
        # TODO(Henry): should something be updated?

    def test_ensure_path_created_for_port_no_path_att(self):
        epg = mock.Mock()
        epg.epg_id = 'epg01'
        eepg = mock.MagicMock(return_value=epg)
        self.mgr.ensure_epg_created_for_network = eepg
        self.mock_ok_get_response('fvRsPathAtt')
        self.mock_responses_for_create('fvRsPathAtt')
        self.mgr.ensure_path_created_for_port('tenant', 'network', 'ubuntu2',
                                              'static')
        # TODO(Henry): the above breaks for an unknown host
        # Just coverage, nothing to verify
        # TODO(Henry): should something be updated?
