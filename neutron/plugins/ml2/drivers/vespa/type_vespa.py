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

from neutron.common import constants as const
from neutron.common import exceptions as exc
from neutron.common import topics
from neutron.common import utils
from neutron.db import agentschedulers_db
from neutron.db import api as db_api
from neutron.db import model_base
from neutron.openstack.common import log
from neutron.plugins.common import utils as plugin_utils
from neutron.plugins.ml2 import driver_api as api
from neutron.plugins.ml2 import rpc
from neutron.plugins.ml2.drivers.vespa import config as conf


LOG = log.getLogger(__name__)


TYPE_VESPA = 'vespa'
VLAN_MIN = 2
VLAN_MAX = 4093


class VespaAllocation(model_base.BASEV2):
    """Vespa vlan allocations per pool."""

    __tablename__ = 'ml2_vespa_allocations'

    network_id = sa.Column(sa.String(64), nullable=False,
                           primary_key=True)
    vlan_id = sa.Column(sa.Integer, nullable=False, primary_key=True,
                        autoincrement=False)
    pool_id = sa.Column(sa.String(64), nullable=False)


class HostPool(model_base.BASEV2):
    """Vespa host pools."""

    __tablename__ = 'ml2_vespa_hostpools'

    host_id = sa.Column(sa.String(64), nullable=False,
                        primary_key=True)
    pool_id = sa.Column(sa.String(255), nullable=False,
                        autoincrement=False)
    switch_ip = sa.Column(sa.String(64), nullable=False,
                        primary_key=False)
    port_id = sa.Column(sa.String(64), nullable=False,
                        primary_key=False)


class VespaTypeDriver(api.TypeDriver,
                      sg_db_rpc.SecurityGroupServerRpcMixin,
                      agentschedulers_db.DhcpAgentSchedulerDbMixin):
    """Manage state for VLAN networks with ML2."""

    def __init__(self):
        """TODO: Connect to the the IFC at init"""
        self.usable_vlans = VLAN_MAX - VLAN_MIN
        self.pools = {}

    def get_type(self):
        return TYPE_VESPA

    def initialize(self):
        self._setup_rpc()
        conf.ML2MechVespaConfig()
        self._host_pools = conf.ML2MechVespaConfig.host_pools
        self._sync_pools()
        LOG.info(_("VespaTypeDriver initialization complete"))

    def _sync_pools(self):
        for pool in self._host_pools:
            self._check_hosts_in_pool(pool, self._host_pools[pool]['hosts'],
                                      self._host_pools[pool]['switch_ip'],
                                      self._host_pools[pool]['port_id'])

    def _setup_rpc(self):
        self.notifier = rpc.AgentNotifierApi(topics.AGENT)
        self.agent_notifiers[const.AGENT_TYPE_DHCP] = (
            dhcp_rpc_agent_api.DhcpAgentNotifyAPI()
        )
        self.callbacks = rpc.RpcCallbacks(self.notifier, None)
        self.topic = topics.PLUGIN
        self.conn = c_rpc.create_connection(new=True)
        self.dispatcher = self.callbacks.create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        self.conn.consume_in_thread()

    def get_host_pools(self):
        session = db_api.get_session()
        # Get a free network segment in the range specified
        bindings = session.query(HostPool).all()

        return bindings

    def add_host_pool(self, host_id, pool_id, switch_ip, port_id):
        session = db_api.get_session()

        hpool = HostPool(host_id=host_id, pool_id=pool_id,
                         switch_ip=switch_ip, port_id=port_id)
        session.add(hpool)
        session.flush()

    def get_host_pool(self, host_id):
        session = db_api.get_session()
        return session.query(HostPool).filter_by(host_id=host_id).first()

    def _check_hosts_in_pool(self, pool_id, hosts, switch_ip, port_id):
        session = db_api.get_session()
        to_add = []
        for host in hosts:
            # Check for a binding
            binding = self.get_host_pool(host)
            if not binding:
                to_add.append(host)
        for host in to_add:
            self.add_host_pool(host, pool_id, switch_ip, port_id)
            
    def allocate_network_segment_per_pool(self, network_id, pool_id):
        session = db_api.get_session()
        # Get a free network segment in the range specified
        bindings = session.query(VespaAllocation).\
                   filter_by(pool_id=pool_id).all()

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
                                    pool_id=pool_id)
            session.add(alloc)
        else:
            raise "No usable segment id found"

    def delete_network_segment_per_pool(self, network_id, pool_id):
        session = db_api.get_session()
        # Get a free network segment in the range specified
        binding = session.query(VespaAllocation).\
            filter_by(pool_id=pool_id).\
            filter_by(network_id=network_id).first()

        session.delete(alloc)

    def get_network_segment_per_pool(self, network_id, pool_id):
        session = db_api.get_session()
        # Get a free network segment in the range specified
        binding = session.query(VespaAllocation).\
            filter_by(pool_id=pool_id).\
            filter_by(network_id=network_id).first()

        return binding

    def allocate_tenant_segment(self, session):
        pass

    def release_segment(self, session, segment):
        pass

    def validate_provider_segment(self, segment):
        pass

    def reserve_provider_segment(self, session, segment):
        pass
