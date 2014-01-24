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

from oslo.config import cfg

from neutron.common import log
from neutron.plugins.ml2.drivers.apic import apic_manager as apic
from neutron.tests import base
from neutron.tests.unit.ml2.drivers import test_cisco_apic_common as mocked


LOG = log.logging.getLogger(__name__)


class TestCiscoApicManager(base.BaseTestCase,
                           mocked.ControllerMixin,
                           mocked.ConfigMixin):

    def setUp(self):
        super(TestCiscoApicManager, self).setUp()
        mocked.ControllerMixin._set_up_mocks(self)
        mocked.ConfigMixin._set_up_mocks(self)

        # Tests are based on authenticated session, so log in here
        self._mock_ok_response('aaaLogin', userName=mocked.APIC_USR)
        self.mgr = apic.APICManager()

        self.addCleanup(mock.patch.stopall)

    def test_mgr_session_login(self):
        login = self.mgr.apic.authentication[0]['aaaLogin']['attributes']
        self.assertEqual(login['userName'], mocked.APIC_USR)

    def test_mgr_session_logout(self):
        self._mock_ok_response('aaaLogout', userName=mocked.APIC_USR)
        self.mgr.apic.logout()
        self.assertIsNone(self.mgr.apic.authentication)
