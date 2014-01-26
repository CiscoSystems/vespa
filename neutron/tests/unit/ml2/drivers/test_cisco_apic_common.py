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

from neutron.common import config as neutron_config
from neutron.plugins.ml2 import config as ml2_config
from neutron.tests.unit import test_api_v2


APIC_HOST = 'fake.controller.local'
APIC_PORT = 7580
APIC_USR = 'notadmin'
APIC_PWD = 'topsecret'

APIC_TENANT = 'citizen14'
APIC_NETWORK = 'network99'
APIC_SUBNET = '10.3.2.1/24'
APIC_L3CTX = 'layer3context'
APIC_AP = 'appProfile001'
APIC_EPG = 'endPointGroup001'

APIC_CONTRACT = 'signedContract'
APIC_SUBJECT = 'testSubject'
APIC_FILTER = 'carbonFilter'
APIC_ENTRY = 'forcedEntry'

APIC_VMMP = 'OpenStack'
APIC_DOMAIN = 'cumuloNimbus'
APIC_PDOM = 'rainStorm'

APIC_NODE_PROF = 'red'
APIC_LEAF = 'green'
APIC_LEAF_TYPE = 'range'
APIC_NODE_BLK = 'blue'
APIC_PORT_PROF = 'yellow'
APIC_PORT_SEL = 'front'
APIC_PORT_TYPE = 'range'
APIC_PORT_BLK1 = 'block01'
APIC_PORT_BLK2 = 'block02'
APIC_ACC_PORT_GRP = 'alpha'
APIC_FUNC_PROF = 'beta'
APIC_ATT_ENT_PROF = 'delta'
APIC_VLAN_NAME = 'gamma'
APIC_VLAN_MODE = 'dynamic'
APIC_VLANID_FROM = 2900
APIC_VLANID_TO = 2999
APIC_VLAN_FROM = 'vlan-%d' % APIC_VLANID_FROM
APIC_VLAN_TO = 'vlan-%d' % APIC_VLANID_TO


class ControllerMixin(object):
    """
    Mock the controller for APIC driver unit tests.
    """

    def __init__(self):
        self.mocked_post = None
        self.mocked_get = None
        self.mock_post_response = None
        self.mock_get_response = None
        self.mocked_response = None
        self.mocked_json_response = None

    def _set_up_mocks(self):
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


class ConfigMixin(object):
    """
    Mock the config for APIC driver unit tests.
    """

    def __init__(self):
        self.mocked_parser = None

    def _set_up_mocks(self):

        # Mock the configuration file
        args = ['--config-file', test_api_v2.etcdir('neutron.conf.test')]
        neutron_config.parse(args=args)

        # Configure the ML2 mechanism drivers and network types
        ml2_opts = {
            'mechanism_drivers': ['apic'],
            'tenant_network_types': ['vlan'],
        }
        for opt, val in ml2_opts.items():
                ml2_config.cfg.CONF.set_override(opt, val, 'ml2')
        self.addCleanup(ml2_config.cfg.CONF.reset)

        # Configure the Cisco APIC mechanism driver
        apic_test_config = {
            'apic_host': APIC_HOST,
            'apic_username': APIC_USR,
            'apic_password': APIC_PWD,
            'apic_port': APIC_PORT,
            'apic_vmm_provider': APIC_VMMP,
            'apic_vmm_domain': APIC_DOMAIN,
            'apic_vlan_ns_name': APIC_VLAN_NAME,
            'apic_vlan_range': '%d:%d' % (APIC_VLANID_FROM, APIC_VLANID_TO),
            'apic_node_profile': APIC_NODE_PROF,
            'apic_entity_profile': APIC_ATT_ENT_PROF,
            'apic_function_profile': APIC_FUNC_PROF,
        }
        for opt, val in apic_test_config.items():
            cfg.CONF.set_override(opt, val, 'ml2_apic')
        self.addCleanup(cfg.CONF.reset)

        apic_switch_cfg = {
            'switch:east01': {'ubuntu1,ubuntu2': [11]},
            'switch:east02': {'rhel01,rhel02': [21]},
        }
        self.mocked_parser = mock.patch.object(cfg,
                                               'MultiConfigParser').start()
        self.mocked_parser.return_value.read.return_value = [apic_switch_cfg]
        self.mocked_parser.return_value.parsed = [apic_switch_cfg]
