# Copyright (c) 2014 Cisco Systems
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
# @author: Henry Gessau, Cisco Systems

import mock
import requests
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
        self.set_up_mocks()
        self.apic = apic.RestClient(mocked.APIC_HOST)
        self.addCleanup(mock.patch.stopall)

    def _mock_authenticate(self, timeout=None):
        if timeout is None:
            timeout = 300
        self.reset_reponses()
        self.mock_response_for_post('aaaLogin', userName=mocked.APIC_USR,
                                    token='X', refreshTimeoutSeconds=timeout)
        self.apic.login(mocked.APIC_USR, mocked.APIC_PWD)

    def test_login_by_instantiation(self):
        self.reset_reponses()
        self.mock_response_for_post('aaaLogin', userName=mocked.APIC_USR,
                                    token='X', refreshTimeoutSeconds='300')
        apic2 = apic.RestClient(mocked.APIC_HOST,
                                usr=mocked.APIC_USR, pwd=mocked.APIC_PWD)
        self.assertIsNotNone(apic2.authentication)
        self.assertEqual(apic2.username, mocked.APIC_USR)

    def test_client_session_login_ok(self):
        self._mock_authenticate()
        self.assertEqual(
            self.apic.authentication['userName'], mocked.APIC_USR)
        self.assertTrue(self.apic.api_base.startswith('http://'))
        self.assertEqual(self.apic.username, mocked.APIC_USR)
        self.assertIsNotNone(self.apic.authentication)
        self.apic = apic.RestClient(mocked.APIC_HOST, mocked.APIC_PORT,
                                    ssl=True)
        self.assertTrue(self.apic.api_base.startswith('https://'))

    def test_client_session_login_fail(self):
        self.mock_error_post_response(wexc.HTTPError.code,
                                      code='599',
                                      text=u'Fake error')
        self.assertRaises(cexc.ApicResponseNotOk, self.apic.login,
                          mocked.APIC_USR, mocked.APIC_PWD)

    def test_client_session_logout_ok(self):
        self.mock_response_for_post('aaaLogout')
        self.apic.logout()
        self.assertIsNone(self.apic.authentication)
        # Multiple signouts should not cause an error
        self.apic.logout()
        self.assertIsNone(self.apic.authentication)

    def test_client_session_logout_fail(self):
        self._mock_authenticate()
        self.mock_error_post_response(wexc.HTTPRequestTimeout.code,
                                      code='123', text='failed')
        self.assertRaises(cexc.ApicResponseNotOk, self.apic.logout)

    def test_query_not_logged_in(self):
        self.apic.authentication = None
        self.assertRaises(cexc.ApicSessionNotLoggedIn,
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

    def test_query_no_response(self):
        self._mock_authenticate()
        requests.Session.get = mock.Mock(return_value=None)
        self.assertRaises(cexc.ApicHostNoResponse,
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

    def test_query_error_response_no_data(self):
        self._mock_authenticate()
        self.mock_error_get_response(wexc.HTTPError.code)  # No error attrs.
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

    def test_generic_get_data(self):
        self._mock_authenticate()
        self.mock_response_for_get('topSystem', name='ifc1')
        top_system = self.apic.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        name = top_system[0]['topSystem']['attributes']['name']
        self.assertEqual(name, 'ifc1')

    def test_session_timeout_refresh_ok(self):
        self._mock_authenticate(timeout=-1)
        # Client will do refresh before getting tenant
        self.mock_response_for_get('aaaRefresh', token='ok',
                                   refreshTimeoutSeconds=300)
        self.mock_response_for_get('fvTenant', name=mocked.APIC_TENANT)
        tenant = self.apic.fvTenant.get(mocked.APIC_TENANT)
        self.assertEqual(tenant['name'], mocked.APIC_TENANT)

    def test_session_timeout_refresh_error(self):
        self._mock_authenticate(timeout=-1)
        self.mock_error_get_response(wexc.HTTPRequestTimeout,
                                     code='503', text=u'timed out')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvTenant.get, mocked.APIC_TENANT)

    def test_session_timeout_refresh_timeout_error(self):
        self._mock_authenticate(timeout=-1)
        # Client will try to get refresh, we fake a refresh error.
        self.mock_error_get_response(wexc.HTTPBadRequest,
                                     code='403',
                                     text=u'Token was invalid. Expired.')
        # Client will then try to re-login.
        self.mock_response_for_post('aaaLogin', userName=mocked.APIC_USR,
                                    token='ok', refreshTimeoutSeconds=300)
        # Finally the client will try to get the tenant.
        self.mock_response_for_get('fvTenant', name=mocked.APIC_TENANT)
        tenant = self.apic.fvTenant.get(mocked.APIC_TENANT)
        self.assertEqual(tenant['name'], mocked.APIC_TENANT)

    def test_lookup_nonexistant_mo(self):
        self._mock_authenticate()
        self.mock_response_for_get('fvTenant')
        self.assertIsNone(self.apic.fvTenant.get(mocked.APIC_TENANT))

    def test_lookup_existing_mo(self):
        self._mock_authenticate()
        self.mock_response_for_get('fvTenant', name='infra')
        tenant = self.apic.fvTenant.get('infra')
        self.assertEqual(tenant['name'], 'infra')

    def test_list_mos_ok(self):
        self._mock_authenticate()
        self.mock_response_for_get('fvTenant', name='t1')
        self.mock_append_to_response('fvTenant', name='t2')
        tlist = self.apic.fvTenant.list_all()
        self.assertIsNotNone(tlist)
        self.assertEqual(len(tlist), 2)

    def test_list_mo_names_ok(self):
        self._mock_authenticate()
        self.mock_response_for_get('fvTenant', name='t1')
        self.mock_append_to_response('fvTenant', name='t2')
        tnlist = self.apic.fvTenant.list_names()
        self.assertIsNotNone(tnlist)
        self.assertEqual(len(tnlist), 2)
        self.assertIn('t1', tnlist)
        self.assertIn('t2', tnlist)

    def test_list_mos_split_class_fail(self):
        self._mock_authenticate()
        self.mock_response_for_get('fvnsEncapBlk', name='Blk1')
        encap_blks = self.apic.fvnsEncapBlk__vlan.list_all()
        self.assertEqual(len(encap_blks), 1)

    def test_delete_mo_ok(self):
        self._mock_authenticate()
        self.mock_response_for_post('fvTenant')
        self.assertFalse(self.apic.fvTenant.delete(mocked.APIC_TENANT))

    def test_create_mo_ok(self):
        self._mock_authenticate()
        self.mock_response_for_post('fvTenant', name=mocked.APIC_TENANT)
        self.mock_response_for_get('fvTenant', name=mocked.APIC_TENANT)
        self.apic.fvTenant.create(mocked.APIC_TENANT)
        tenant = self.apic.fvTenant.get(mocked.APIC_TENANT)
        self.assertEqual(tenant['name'], mocked.APIC_TENANT)

    def test_create_mo_already_exists(self):
        self._mock_authenticate()
        self.mock_error_post_response(wexc.HTTPBadRequest,
                                      code='103',
                                      text=u'Fake 103 error')
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.vmmProvP.create, mocked.APIC_VMMP)

    def test_create_mo_with_prereq(self):
        self._mock_authenticate()
        self.mock_response_for_post('fvTenant', name=mocked.APIC_TENANT)
        self.mock_response_for_post('fvBD', name=mocked.APIC_NETWORK)
        self.mock_response_for_get('fvBD', name=mocked.APIC_NETWORK)
        bd_args = mocked.APIC_TENANT, mocked.APIC_NETWORK
        self.apic.fvBD.create(*bd_args)
        network = self.apic.fvBD.get(*bd_args)
        self.assertEqual(network['name'], mocked.APIC_NETWORK)

    def test_create_mo_prereq_exists(self):
        self._mock_authenticate()
        self.mock_response_for_post('vmmDomP', name=mocked.APIC_DOMAIN)
        self.mock_response_for_get('vmmDomP', name=mocked.APIC_DOMAIN)
        self.apic.vmmDomP.create(mocked.APIC_VMMP, mocked.APIC_DOMAIN)
        dom = self.apic.vmmDomP.get(mocked.APIC_VMMP, mocked.APIC_DOMAIN)
        self.assertEqual(dom['name'], mocked.APIC_DOMAIN)

    def test_create_mo_fails(self):
        self._mock_authenticate()
        self.mock_response_for_post('fvTenant', name=mocked.APIC_TENANT)
        self.mock_error_post_response(wexc.HTTPBadRequest,
                                      code='not103',
                                      text=u'Fake not103 error')
        bd_args = mocked.APIC_TENANT, mocked.APIC_NETWORK
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvBD.create, *bd_args)

    def test_update_mo(self):
        self._mock_authenticate()
        self.mock_response_for_post('fvTenant', name=mocked.APIC_TENANT)
        self.mock_response_for_get('fvTenant', name=mocked.APIC_TENANT,
                                   more='extra')
        self.apic.fvTenant.update(mocked.APIC_TENANT, more='extra')
        tenant = self.apic.fvTenant.get(mocked.APIC_TENANT)
        self.assertEqual(tenant['name'], mocked.APIC_TENANT)
        self.assertEqual(tenant['more'], 'extra')

    def test_attr_fail_empty_list(self):
        self._mock_authenticate()
        self.mock_response_for_get('fvTenant')  # No attrs for tenant.
        self.assertIsNone(self.apic.fvTenant.get(mocked.APIC_TENANT))

    def test_attr_fail_other_obj(self):
        self._mock_authenticate()
        self.mock_response_for_get('other', name=mocked.APIC_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(mocked.APIC_TENANT))
