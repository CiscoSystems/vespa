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
from webob import exc as wexc

from neutron.common import log
from neutron.plugins.ml2.drivers.apic import apic_client as apic
from neutron.plugins.ml2.drivers.cisco import exceptions as cexc
from neutron.tests import base
from neutron.tests.unit.ml2.drivers import test_cisco_apic_common as mocked


LOG = log.logging.getLogger(__name__)


class TestCiscoApicClient(base.BaseTestCase, mocked.ControllerMixin):

    def setUp(self):
        super(TestCiscoApicClient, self).setUp()
        self._set_up_mocks()
        self.apic = apic.RestClient(mocked.APIC_HOST)
        self.addCleanup(mock.patch.stopall)

    def _mock_authenticate(self):
        self.apic.login(mocked.APIC_USR, mocked.APIC_PWD)
        self.apic.authentication = 'logged in'

    def test_client_session_login_ok(self):
        self._mock_ok_response('aaaLogin', userName=mocked.APIC_USR)
        self.apic = apic.RestClient(mocked.APIC_HOST, mocked.APIC_PORT,
                                    mocked.APIC_USR, mocked.APIC_PWD)
        self.assertEqual(
            self.apic.authentication[0]['aaaLogin']['attributes']['userName'],
            mocked.APIC_USR)
        self.assertTrue(self.apic.api_base.startswith('http://'))
        self.assertEqual(self.apic.username, mocked.APIC_USR)
        self.assertIsNotNone(self.apic.authentication)
        self.apic = apic.RestClient(mocked.APIC_HOST, mocked.APIC_PORT,
                                    ssl=True)
        self.assertTrue(self.apic.api_base.startswith('https://'))

    def test_client_session_login_fail(self):
        self._mock_error_response(wexc.HTTPError.code,
                                  err_code='599',
                                  err_text=u'Fake error')
        self.assertRaises(cexc.ApicResponseNotOk, self.apic.login,
                          mocked.APIC_USR, mocked.APIC_PWD)

    def test_client_session_logout_ok(self):
        self._mock_ok_response('aaaLogout', userName=mocked.APIC_USR)
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
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

    def test_query_no_response(self):
        self._mock_authenticate()
        self.mocked_get.return_value = None
        self.assertRaises(cexc.ApicHostNoResponse,
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

    def test_query_error_response_no_data(self):
        self._mock_authenticate()
        self._mock_error_response(wexc.HTTPError.code)
        del self.mocked_response[:]
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

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
        self.assertIsNone(self.apic.fvTenant.get(mocked.APIC_TENANT))

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
        self.assertFalse(self.apic.fvTenant.delete(mocked.APIC_TENANT))

    def test_delete_mo_fail(self):
        self._mock_authenticate()
        self._mock_ok_response('fvTenant', status='fail')
        self.assertFalse(self.apic.fvTenant.delete(mocked.APIC_TENANT))

    def test_create_mo_ok(self):
        self._mock_authenticate()
        self.apic.fvTenant.create(mocked.APIC_TENANT)
        self._mock_ok_response('fvTenant', name=mocked.APIC_TENANT)
        tenant = self.apic.fvTenant.get(mocked.APIC_TENANT)
        self.assertEqual(tenant['name'], mocked.APIC_TENANT)

    def test_create_mo_already_exists(self):
        self._mock_authenticate()
        self._mock_error_response(wexc.HTTPBadRequest,
                                  err_code='103',
                                  err_text=u'Fake 103 error')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.vmmProvP.create, mocked.APIC_VMMP)

    def test_create_mo_with_prereq(self):
        self._mock_authenticate()
        bd_args = mocked.APIC_TENANT, mocked.APIC_NETWORK
        self.apic.fvBD.create(*bd_args)
        self._mock_ok_response('fvBD', name=mocked.APIC_NETWORK)
        network = self.apic.fvBD.get(*bd_args)
        self.assertEqual(network['name'], mocked.APIC_NETWORK)

    def test_create_mo_prereq_exists(self):
        self._mock_authenticate()
        self.apic.vmmDomP.create(mocked.APIC_VMMP, mocked.APIC_DOMAIN)
        self._mock_ok_response('vmmDomP', name=mocked.APIC_DOMAIN)
        dom = self.apic.vmmDomP.get(mocked.APIC_VMMP, mocked.APIC_DOMAIN)
        self.assertEqual(dom['name'], mocked.APIC_DOMAIN)

    def test_create_mo_fails(self):
        self._mock_authenticate()
        bd_args = mocked.APIC_TENANT, mocked.APIC_NETWORK
        self._mock_error_response(wexc.HTTPBadRequest,
                                  err_code='not103',
                                  err_text=u'Fake not103 error')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvBD.create, *bd_args)

    def test_update_mo(self):
        self._mock_authenticate()
        self.apic.fvTenant.update(mocked.APIC_TENANT, more='extra')
        self._mock_ok_response('fvTenant', name=mocked.APIC_TENANT,
                               more='extra')
        tenant = self.apic.fvTenant.get(mocked.APIC_TENANT)
        self.assertEqual(tenant['name'], mocked.APIC_TENANT)
        self.assertEqual(tenant['more'], 'extra')

    def test_attr_fail_empty_list(self):
        self._mock_authenticate()
        self._mock_ok_response(None)
        self.assertIsNone(self.apic.fvTenant.get(mocked.APIC_TENANT))

    def test_attr_fail_empty_obj(self):
        self._mock_authenticate()
        self._mock_ok_response({})
        self.assertIsNone(self.apic.fvTenant.get(mocked.APIC_TENANT))
