# Copyright (c) 2014 Cisco Systems Inc.
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
# @author: Arvind Somya (asomya@cisco.com), Cisco Systems Inc.

import sqlalchemy as sa

from neutron.db import api as db_api
from neutron.db import model_base


class NetworkEPG(model_base.BASEV2):
    """EPG's created on the apic per network."""

    __tablename__ = 'ml2_apic_epgs'

    network_id = sa.Column(sa.String(64), nullable=False,
                           primary_key=True)
    epg_id = sa.Column(sa.String(64), nullable=False)
    segmentation_id = sa.Column(sa.String(64), nullable=False)
    provider = sa.Column(sa.Boolean, default=False)


class PortProfile(model_base.BASEV2):
    """Port profiles created on the APIC."""

    __tablename__ = 'ml2_apic_port_profiles'

    node_id = sa.Column(sa.String(64), nullable=False, primary_key=True)
    profile_id = sa.Column(sa.String(64), nullable=False)
    hpselc_id = sa.Column(sa.String(64), nullable=False)
    module = sa.Column(sa.String(10), nullable=False)
    from_port = sa.Column(sa.Integer(10), nullable=False)
    to_port = sa.Column(sa.Integer(10), nullable=False)


class TenantContract(model_base.BASEV2):
    """Contracts (and Filters) created on the APIC."""

    __tablename__ = 'ml2_apic_contracts'

    tenant_id = sa.Column(sa.String(64), nullable=False, primary_key=True)
    contract_id = sa.Column(sa.String(64), nullable=False)
    filter_id = sa.Column(sa.String(64), nullable=False)


class ApicDbModel(object):
    def __init__(self):
        self.session = db_api.get_session()

    def get_port_profile_for_node(self, node_id):
        return self.session.query(PortProfile).filter_by(
            node_id=node_id).first()

    def get_profile_for_module_and_ports(self, node_id, profile_id,
                                         module, from_port, to_port):
        return self.session.query(PortProfile).filter_by(
            node_id=node_id,
            module=module,
            profile_id=profile_id,
            from_port=from_port,
            to_port=to_port).first()

    def get_profile_for_module(self, node_id, profile_id, module):
        return self.session.query(PortProfile).filter_by(
            node_id=node_id,
            profile_id=profile_id,
            module=module).first()

    def add_profile_for_module_and_ports(self, node_id, profile_id,
                                         hpselc_id, module,
                                         from_port, to_port):
        row = PortProfile(node_id=node_id, profile_id=profile_id,
                          hpselc_id=hpselc_id, module=module,
                          from_port=from_port, to_port=to_port)
        self.session.add(row)
        self.session.flush()

    def get_provider_contract(self):
        epg = self.session.query(NetworkEPG).filter_by(
            provider=True).first()
        if epg:
            return True

        return False

    def set_provider_contract(self, epg_id):
        epg = self.session.query(NetworkEPG).filter_by(
            epg_id=epg_id).first()
        if epg:
            epg.provider = True
            self.session.merge(epg)
            self.session.flush()
            return epg

        return False

    def unset_provider_contract(self, epg_id):
        epg = self.session.query(NetworkEPG).filter_by(
            epg_id=epg_id).first()
        if epg:
            epg.provider = False
            self.session.merge(epg)
            self.session.flush()
            return epg

        return False

    def get_an_epg(self, exception):
        epg = self.session.query(NetworkEPG).filter(
            NetworkEPG.epg_id != exception).first()
        if epg:
            return epg

    def get_epg_for_network(self, network_id):
        return self.session.query(NetworkEPG).filter_by(
            network_id=network_id).first()

    def write_epg_for_network(self, network_id, epg_uid, segmentation_id='1'):
        epg = NetworkEPG(network_id=network_id, epg_id=epg_uid,
                         segmentation_id=segmentation_id)
        self.session.add(epg)
        self.session.flush()
        return epg

    def delete_epg(self, epg):
        self.session.delete(epg)
        self.session.flush()

    def get_contract_for_tenant(self, tenant_id):
        return self.session.query(TenantContract).filter_by(
            tenant_id=tenant_id).first()

    def write_contract_for_tenant(self, tenant_id, contract_id, filter_id):
        contract = TenantContract(tenant_id=tenant_id,
                                  contract_id=contract_id,
                                  filter_id=filter_id)
        self.session.add(contract)
        self.session.flush()

        return contract
