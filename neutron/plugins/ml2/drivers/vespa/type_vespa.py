# Copyright (c) 2013 OpenStack Foundation
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

import sys

from oslo.config import cfg
import sqlalchemy as sa

from neutron.agent import securitygroups_rpc as sg_rpc
from neutron.api.rpc.agentnotifiers import dhcp_rpc_agent_api
from neutron.db import securitygroups_rpc_base as sg_db_rpc
from neutron.openstack.common import rpc as c_rpc

from neutron.common import constants as q_const
from neutron.common import exceptions as exc
from neutron.common import utils
from neutron.db import api as db_api
from neutron.db import model_base
from neutron.openstack.common import log
from neutron.plugins.common import utils as plugin_utils
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import rpc


LOG = log.getLogger(__name__)


TYPE_VESPA = 'vespa'
VLAN_MIN = 2
VLAN_MAX = 4093


class VespaAllocation(model_base.BASEV2):
    """Vespa vlan allocations per host."""

    __tablename__ = 'ml2_vespa_allocations'

    network_id = sa.Column(sa.String(64), nullable=False,
                           primary_key=True)
    vlan_id = sa.Column(sa.Integer, nullable=False, primary_key=True,
                        autoincrement=False)
    host_id = sa.Column(sa.String(255), nullable=False, primary_key=True)


class VespaTypeDriver(api.TypeDriver):
    """Manage state for VLAN networks with ML2."""

    def __init__(self):
        """TODO: Connect to the the IFC at init"""
        self.usable_vlans = VLAN_MAX - VLAN_MIN

    def get_type(self):
        return TYPE_VESPA

    def initialize(self):
        self._sync_vlan_allocations()
        self._setup_rpc()
        LOG.info(_("VlanTypeDriver initialization complete"))

     def _setup_rpc(self):
        self.notifier = rpc.AgentNotifierApi(topics.AGENT)
        self.agent_notifiers[const.AGENT_TYPE_DHCP] = (
            dhcp_rpc_agent_api.DhcpAgentNotifyAPI()
        )
        self.callbacks = rpc.RpcCallbacks(self.notifier, self.type_manager)
        self.topic = topics.PLUGIN
        self.conn = c_rpc.create_connection(new=True)
        self.dispatcher = self.callbacks.create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        self.conn.consume_in_thread()

    def allocate_network_segment_per_host(session, network_id, host_id):
        session = session or db.get_session()
        # Get a free network segment in the range specified
        bindings = session.query(VespaAllocation).\
                   filter_by(host_id=host_id).all()

        allocated_ids = []
        for binding in bindings:
            allocated_ids.append(binding.vlan_id)

        # Find a segment in range that's not allocated
        allocated_segment = None
        for segment in range(VLAN_MIN, VLAN_MAX):
            if segment not in allocated_ids:
                allocated_segment = segment
                break

        if allocated_segment:
            alloc = VespaAllocation(network_id=network_id,
                                    vlan_id=allocated_segment,
                                    host_id=host_id)
            session.add(alloc)
        else:
            raise "No usable segment id found"

    def delete_network_segment_per_host(session, network_id, host_id):
        session = session or db.get_session()
        # Get a free network segment in the range specified
        binding = session.query(VespaAllocation).\
            filter_by(host_id=host_id).\
            filter_by(network_id=network_id).first()

        session.delete(alloc)

    def get_network_segmen_per_host(session, network_id, host_id):
        session = session or db.get_session()
        # Get a free network segment in the range specified
        binding = session.query(VespaAllocation).\
            filter_by(host_id=host_id).\
            filter_by(network_id=network_id).first()

        return binding

    def allocate_tenant_segment(self, session):
        pass

    def release_segment(self, session, segment):
        pass
