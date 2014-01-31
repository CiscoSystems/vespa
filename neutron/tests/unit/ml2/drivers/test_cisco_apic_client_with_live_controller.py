# Copyright (c) 2014 Cisco Systems
#
# @author: Henry Gessau, Cisco Systems
#
#  ______        _   _       _     _____                           _ _
#  |  _  \      | \ | |     | |   /  __ \                         (_) |
#  | | | |___   |  \| | ___ | |_  | /  \/ ___  _ __ ___  _ __ ___  _| |_
#  | | | / _ \  | . ` |/ _ \| __| | |    / _ \| '_ ` _ \| '_ ` _ \| | __|
#  | |/ / (_) | | |\  | (_) | |_  | \__/\ (_) | | | | | | | | | | | | |_
#  |___/ \___/  \_| \_/\___/ \__|  \____/\___/|_| |_| |_|_| |_| |_|_|\__|
#  _____ _     _       _          _   _            _                   _
# |_   _| |   (_)     | |        | \ | |          | |                 | |
#   | | | |__  _ ___  | |_ ___   |  \| | ___ _   _| |_ _ __ ___  _ __ | |
#   | | | '_ \| / __| | __/ _ \  | . ` |/ _ \ | | | __| '__/ _ \| '_ \| |
#   | | | | | | \__ \ | || (_) | | |\  |  __/ |_| | |_| | | (_) | | | |_|
#   \_/ |_| |_|_|___/  \__\___/  \_| \_/\___|\__,_|\__|_|  \___/|_| |_(_)
#

import time

from neutron.common import log
from neutron.plugins.ml2.drivers.apic import apic_client as apic
from neutron.plugins.ml2.drivers.cisco import exceptions as cexc
from neutron.tests import base
from neutron.tests.unit.ml2.drivers import test_cisco_apic_common as test


LOG = log.logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TODO(Henry): this should go in tempest 3rd party, not unit test

APIC0_HOST = '172.21.32.71'   # was .116, .120, .71
APIC0_PORT = '7580'           # was 8000
APIC1_HOST = '172.21.128.43'
APIC2_HOST = '172.21.128.44'
APIC3_HOST = '172.21.128.45'
APIC4_HOST = '172.21.128.10'
APIC_ADMIN = 'admin'
APIC_PWD = 'ins3965!'

APIC_VMMP_OS = 'VMware'  # Change to 'OpenStack' when APIC supports it


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
        self.apic.fvCtx.delete(test.APIC_TENANT, test.APIC_L3CTX)
        self.apic.fvAEPg.delete(test.APIC_TENANT, test.APIC_AP,
                                test.APIC_EPG)
        self.apic.fvBD.delete(test.APIC_TENANT, test.APIC_NETWORK)
        self.apic.fvRsCtx.delete(test.APIC_TENANT, test.APIC_NETWORK)
        self.apic.fvCtx.delete(test.APIC_TENANT, test.APIC_L3CTX)
        self.apic.fvTenant.delete(test.APIC_TENANT)

    def delete_dom_test_objects(self):
        """In case previous test attempts didn't clean up."""
        leaf_node_args = (test.APIC_NODE_PROF,
                          test.APIC_LEAF,
                          test.APIC_LEAF_TYPE)
        node_blk_args = leaf_node_args + (test.APIC_NODE_BLK,)
        lhps_args = (test.APIC_PORT_PROF,
                     test.APIC_PORT_SEL,
                     test.APIC_PORT_TYPE)
        vinst_args = test.APIC_VLAN_NAME, test.APIC_VLAN_MODE
        eb_args = vinst_args + (test.APIC_VLAN_FROM,
                                test.APIC_VLAN_TO)
        epg_args = test.APIC_TENANT, test.APIC_AP, test.APIC_EPG
        dom_args = APIC_VMMP_OS, test.APIC_DOMAIN
        domain = self.apic.vmmDomP.get(*dom_args)
        dom_dn = domain and domain['dn'] or None
        port_profile = self.apic.infraAccPortP.get(test.APIC_PORT_PROF)
        pp_dn = port_profile and port_profile['dn'] or None
        self.apic.fvnsEncapBlk__vlan.delete(*eb_args)
        self.apic.fvnsVlanInstP.delete(*vinst_args)
        if dom_dn:
            self.apic.infraRsDomP.delete(test.APIC_ATT_ENT_PROF, dom_dn)
        self.apic.infraAttEntityP.delete(test.APIC_ATT_ENT_PROF)
        self.apic.infraRsAccBaseGrp.delete(*lhps_args)
        self.apic.infraAccPortGrp.delete(test.APIC_ACC_PORT_GRP)
        port_block2_args = lhps_args + (test.APIC_PORT_BLK2,)
        self.apic.infraPortBlk.delete(*port_block2_args)
        port_block1_args = lhps_args + (test.APIC_PORT_BLK1,)
        self.apic.infraPortBlk.delete(*port_block1_args)
        self.apic.infraHPortS.delete(*lhps_args)
        if pp_dn:
            self.apic.infraRsAccPortP.delete(test.APIC_NODE_PROF, pp_dn)
        self.apic.infraAccPortP.delete(test.APIC_PORT_PROF)
        self.apic.infraNodeBlk.delete(*node_blk_args)
        self.apic.infraLeafS.delete(*leaf_node_args)
        self.apic.infraNodeP.delete(test.APIC_NODE_PROF)
        if dom_dn:
            dom_ref_args = epg_args + (dom_dn,)
            self.apic.fvRsDomAtt.delete(*dom_ref_args)  # Rs
        self.apic.vmmDomP.delete(*dom_args)
        self.apic.fvAEPg.delete(*epg_args)
        self.apic.fvTenant.delete(test.APIC_TENANT)

    def test_cisco_apic_client_session(self):
        for t in range(305, -1, -5):
            print 'Waiting', t
            time.sleep(5)
        print
        print
        print 'Here goes ...'
        self.delete_epg_test_objects()
        self.assertIsNotNone(self.apic.authentication)

    def test_query_top_system(self):
        top_system = self.apic.get_data('class/topSystem')
        self.assertIsNotNone(top_system)
        name = top_system[0]['topSystem']['attributes']['name']
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)

    def test_lookup_nonexistant_tenant(self):
        self.apic.fvTenant.delete(test.APIC_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(test.APIC_TENANT))

    def test_lookup_existing_tenant(self):
        tenant = self.apic.fvTenant.get('infra')
        self.assertEqual(tenant['name'], 'infra')

    def test_lookup_nonexistant_network(self):
        self.assertIsNone(self.apic.fvBD.get('LarryKing', 'CableNews'))

    def test_create_tenant_network_subnet(self):
        bd_args = test.APIC_TENANT, test.APIC_NETWORK
        subnet_args = (test.APIC_TENANT,
                       test.APIC_NETWORK,
                       test.APIC_SUBNET)
        self.apic.fvSubnet.delete(*subnet_args)
        self.apic.fvBD.delete(*bd_args)
        self.apic.fvTenant.delete(test.APIC_TENANT)
        # ----
        self.apic.fvSubnet.create(*subnet_args)
        new_sn = self.apic.fvSubnet.get(*subnet_args)
        self.assertEqual(new_sn['ip'], test.APIC_SUBNET)
        new_network = self.apic.fvBD.get(*bd_args)
        self.assertEqual(new_network['name'], test.APIC_NETWORK)
        tenant = self.apic.fvTenant.get(test.APIC_TENANT)
        self.assertEqual(tenant['name'], test.APIC_TENANT)
        # ----
        self.apic.fvSubnet.delete(*subnet_args)
        self.assertIsNone(self.apic.fvSubnet.get(*subnet_args))
        self.apic.fvBD.delete(*bd_args)
        self.assertIsNone(self.apic.fvBD.get(*bd_args))
        self.apic.fvTenant.delete(test.APIC_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(test.APIC_TENANT))

    def test_create_bd_with_subnet_and_l3ctx(self):
        self.delete_epg_test_objects()
        self.addCleanup(self.delete_epg_test_objects)
        # ----
        bd_args = test.APIC_TENANT, test.APIC_NETWORK
        subnet_args = (test.APIC_TENANT,
                       test.APIC_NETWORK,
                       test.APIC_SUBNET)
        self.apic.fvSubnet.create(*subnet_args)
        new_sn = self.apic.fvSubnet.get(*subnet_args)
        self.assertEqual(new_sn['ip'], test.APIC_SUBNET)
        bd = self.apic.fvBD.get(*bd_args)
        self.assertEqual(bd['name'], test.APIC_NETWORK)
        tenant = self.apic.fvTenant.get(test.APIC_TENANT)
        self.assertEqual(tenant['name'], test.APIC_TENANT)
        # create l3ctx on tenant
        ctx_args = test.APIC_TENANT, test.APIC_L3CTX
        self.apic.fvCtx.create(*ctx_args)
        new_l3ctx = self.apic.fvCtx.get(*ctx_args)
        self.assertEqual(new_l3ctx['name'], test.APIC_L3CTX)
        # assocate l3ctx with mock_apic.TEST_NETWORK
        self.apic.fvRsCtx.create(*bd_args, tnFvCtxName=test.APIC_L3CTX)
        rsctx = self.apic.fvRsCtx.get(*bd_args)
        self.assertEqual(rsctx['tnFvCtxName'], test.APIC_L3CTX)
        # ----
        self.assertRaises(cexc.ApicResponseNotOk,
                          self.apic.fvRsCtx.delete, *bd_args)
        self.apic.fvCtx.delete(*ctx_args)
        self.assertIsNone(self.apic.fvCtx.get(*ctx_args))
        # tenant and BD should still exist
        tenant = self.apic.fvTenant.get(test.APIC_TENANT)
        self.assertEqual(tenant['name'], test.APIC_TENANT)
        bd = self.apic.fvBD.get(*bd_args)
        self.assertEqual(bd['name'], test.APIC_NETWORK)
        # cleanup deletes the rest

    def test_create_epg_with_bd(self):
        self.delete_epg_test_objects()
        self.addCleanup(self.delete_epg_test_objects)
        # ----
        bd_args = test.APIC_TENANT, test.APIC_NETWORK
        epg_args = test.APIC_TENANT, test.APIC_AP, test.APIC_EPG
        self.apic.fvBD.create(*bd_args)
        bd = self.apic.fvBD.get(*bd_args)
        self.assertEqual(bd['name'], test.APIC_NETWORK)
        self.apic.fvAEPg.create(*epg_args)
        epg = self.apic.fvAEPg.get(*epg_args)
        self.assertEqual(epg['name'], test.APIC_EPG)
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
        bd_args = test.APIC_TENANT, test.APIC_NETWORK
        subnet_args = (test.APIC_TENANT,
                       test.APIC_NETWORK,
                       test.APIC_SUBNET)
        self.apic.fvSubnet.create(*subnet_args)
        snlist = self.apic.fvSubnet.list_all()
        self.assertGreater(len(snlist), 0)
        self.apic.fvSubnet.delete(*subnet_args)
        self.apic.fvBD.delete(*bd_args)
        self.apic.fvTenant.delete(test.APIC_TENANT)

    def test_list_app_profiles(self):
        aplist = self.apic.fvAp.list_all()
        self.assertGreater(len(aplist), 0)

    def test_list_epgs(self):
        elist = self.apic.fvAEPg.list_all()
        self.assertGreater(len(elist), 0)

    def test_create_and_lookup_contract(self):
        self.apic.vzBrCP.create(test.APIC_TENANT, test.APIC_CONTRACT)
        new_contract = self.apic.vzBrCP.get(test.APIC_TENANT,
                                            test.APIC_CONTRACT)
        self.assertEqual(new_contract['name'], test.APIC_CONTRACT)
        tenant = self.apic.fvTenant.get(test.APIC_TENANT)
        self.assertEqual(tenant['name'], test.APIC_TENANT)
        self.apic.vzBrCP.delete(test.APIC_TENANT, test.APIC_CONTRACT)
        self.assertIsNone(self.apic.vzBrCP.get(test.APIC_TENANT,
                                               test.APIC_CONTRACT))
        self.apic.fvTenant.delete(test.APIC_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(test.APIC_TENANT))

    def test_create_and_lookup_entry(self):
        filter_args = (test.APIC_TENANT,
                       test.APIC_FILTER)
        entry_args = (test.APIC_TENANT,
                      test.APIC_FILTER,
                      test.APIC_ENTRY)
        self.apic.vzEntry.delete(*entry_args)
        self.apic.fvTenant.delete(test.APIC_TENANT)
        self.apic.vzEntry.create(*entry_args)
        new_entry = self.apic.vzEntry.get(*entry_args)
        self.assertEqual(new_entry['name'], test.APIC_ENTRY)
        new_filter = self.apic.vzFilter.get(*filter_args)
        self.assertEqual(new_filter['name'], test.APIC_FILTER)
        tenant = self.apic.fvTenant.get(test.APIC_TENANT)
        self.assertEqual(tenant['name'], test.APIC_TENANT)
        self.apic.vzEntry.update(*entry_args, prot='udp', dToPort='pop3')
        self.apic.vzEntry.delete(*entry_args)
        self.assertIsNone(self.apic.vzEntry.get(*entry_args))
        self.apic.vzFilter.delete(*filter_args)
        self.assertIsNone(self.apic.vzFilter.get(*filter_args))
        self.apic.fvTenant.delete(test.APIC_TENANT)
        self.assertIsNone(self.apic.fvTenant.get(test.APIC_TENANT))

    def test_create_physical_domain(self):
        # Create a Physical Domain Profile
        self.apic.physDomP.create(test.APIC_PDOM)
        pdom = self.apic.physDomP.get(test.APIC_PDOM)
        self.assertEqual(pdom['dn'], "uni/phys-%s" % test.APIC_PDOM)
        self.apic.physDomP.delete(test.APIC_PDOM)
        self.assertIsNone(self.apic.physDomP.get(test.APIC_PDOM))

    def test_create_domain_vlan_node_mappings(self):
        self.delete_dom_test_objects()
        self.addCleanup(self.delete_dom_test_objects)

        # Create a VMM Domain for the cloud
        dom_args = APIC_VMMP_OS, test.APIC_DOMAIN
        self.apic.vmmDomP.create(*dom_args)
        domain = self.apic.vmmDomP.get(*dom_args)
        self.assertEqual(domain['name'], test.APIC_DOMAIN)

        # Get the DN of the VMM domain
        dom_dn = domain['dn']
        self.assertEqual(dom_dn, 'uni/vmmp-%s/dom-%s' % dom_args)

        # Associate the domain with an EPG
        epg_args = test.APIC_TENANT, test.APIC_AP, test.APIC_EPG
        dom_ref_args = epg_args + (dom_dn,)
        self.apic.fvRsDomAtt.create(*dom_ref_args)
        dom_ref = self.apic.fvRsDomAtt.get(*dom_ref_args)
        self.assertEqual(dom_ref['tDn'], dom_dn)

        # Create a Node Profile
        self.apic.infraNodeP.create(test.APIC_NODE_PROF)
        node_profile = self.apic.infraNodeP.get(test.APIC_NODE_PROF)
        self.assertEqual(node_profile['name'], test.APIC_NODE_PROF)

        # Add a Leaf Node Selector to the Node Profile
        leaf_node_args = (test.APIC_NODE_PROF,
                          test.APIC_LEAF,
                          test.APIC_LEAF_TYPE)
        self.apic.infraLeafS.create(*leaf_node_args)
        leaf_node = self.apic.infraLeafS.get(*leaf_node_args)
        self.assertEqual(leaf_node['name'], test.APIC_LEAF)

        # Add a Node Block to the Leaf Node Selector
        node_blk_args = leaf_node_args + (test.APIC_NODE_BLK,)
        self.apic.infraNodeBlk.create(*node_blk_args, from_='13', to_='13')
        node_block = self.apic.infraNodeBlk.get(*node_blk_args)
        self.assertEqual(node_block['name'], test.APIC_NODE_BLK)

        # Create a Port Profile and get its DN
        self.apic.infraAccPortP.create(test.APIC_PORT_PROF)
        port_profile = self.apic.infraAccPortP.get(test.APIC_PORT_PROF)
        pp_dn = port_profile['dn']
        self.assertEqual(pp_dn,
                         'uni/infra/accportprof-%s' % test.APIC_PORT_PROF)

        # Associate the Port Profile with the Node Profile
        self.apic.infraRsAccPortP.create(test.APIC_NODE_PROF, pp_dn)
        ppref = self.apic.infraRsAccPortP.get(test.APIC_NODE_PROF, pp_dn)
        self.assertEqual(ppref['tDn'], pp_dn)

        # Add a Leaf Host Port Selector to the Port Profile
        lhps_args = (test.APIC_PORT_PROF,
                     test.APIC_PORT_SEL,
                     test.APIC_PORT_TYPE)
        self.apic.infraHPortS.create(*lhps_args)
        lhps = self.apic.infraHPortS.get(*lhps_args)
        self.assertEqual(lhps['name'], test.APIC_PORT_SEL)

        # Add a Port Block to the Leaf Host Port Selector
        port_block1_args = lhps_args + (test.APIC_PORT_BLK1,)
        self.apic.infraPortBlk.create(
            *port_block1_args,
            fromCard='1', toCard='1', fromPort='10', toPort='12')
        port_block1 = self.apic.infraPortBlk.get(*port_block1_args)
        self.assertEqual(port_block1['name'], test.APIC_PORT_BLK1)

        # Add another Port Block to the Leaf Host Port Selector
        port_block2_args = lhps_args + (test.APIC_PORT_BLK2,)
        self.apic.infraPortBlk.create(
            *port_block2_args,
            fromCard='1', toCard='1', fromPort='20', toPort='22')
        port_block2 = self.apic.infraPortBlk.get(*port_block2_args)
        self.assertEqual(port_block2['name'], test.APIC_PORT_BLK2)

        # Create an Access Port Group and get its DN
        self.apic.infraAccPortGrp.create(test.APIC_ACC_PORT_GRP)
        access_pg = self.apic.infraAccPortGrp.get(test.APIC_ACC_PORT_GRP)
        self.assertTrue(access_pg)
        apg_dn = access_pg['dn']
        self.assertEqual(apg_dn, 'uni/infra/funcprof/accportgrp-%s' %
                                 test.APIC_ACC_PORT_GRP)

        # Associate the Access Port Group with Leaf Host Port Selector
        self.apic.infraRsAccBaseGrp.create(*lhps_args, tDn=apg_dn)
        apg_ref = self.apic.infraRsAccBaseGrp.get(*lhps_args)
        self.assertEqual(apg_ref['tDn'], apg_dn)

        # Create an Attached Entity Profile
        self.apic.infraAttEntityP.create(test.APIC_ATT_ENT_PROF)
        ae_profile = self.apic.infraAttEntityP.get(test.APIC_ATT_ENT_PROF)
        aep_dn = ae_profile['dn']
        self.assertEqual(aep_dn,
                         'uni/infra/attentp-%s' % test.APIC_ATT_ENT_PROF)

        # Associate the cloud domain with the Attached Entity Profile
        self.apic.infraRsDomP.create(test.APIC_ATT_ENT_PROF, dom_dn)
        dom_ref = self.apic.infraRsDomP.get(test.APIC_ATT_ENT_PROF, dom_dn)
        self.assertEqual(dom_ref['tDn'], dom_dn)

        # Associate the aep with the apg
        self.apic.infraRsAttEntP.create(test.APIC_ACC_PORT_GRP, tDn=aep_dn)
        aep_ref = self.apic.infraRsAttEntP.get(test.APIC_ACC_PORT_GRP)
        self.assertEqual(aep_ref['tDn'], aep_dn)

        # Create a Vlan Instance Profile
        vinst_args = test.APIC_VLAN_NAME, test.APIC_VLAN_MODE
        self.apic.fvnsVlanInstP.create(*vinst_args)
        vlan_instp = self.apic.fvnsVlanInstP.get(*vinst_args)
        self.assertEqual(vlan_instp['name'], test.APIC_VLAN_NAME)

        # Create an Encap Block for the Vlan Instance Profile
        eb_args = vinst_args + (test.APIC_VLAN_FROM,
                                test.APIC_VLAN_TO)
        eb_data = {'name': 'encap',
                   'from': test.APIC_VLAN_FROM,
                   'to': test.APIC_VLAN_TO}
        self.apic.fvnsEncapBlk__vlan.create(*eb_args, **eb_data)
        encap_blk = self.apic.fvnsEncapBlk__vlan.get(*eb_args)
        self.assertEqual(encap_blk['name'], 'encap')
        self.assertEqual(encap_blk['from'], test.APIC_VLAN_FROM)
        self.assertEqual(encap_blk['to'], test.APIC_VLAN_TO)

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
        self.assertIsNone(eppd)  # TODO(Henry): fix this
        #self.assertTrue(eppd)
        #eppd_dn = eppd['dn']
        #print eppd_dn

    def clean_up_contracts_filters_subjects_etc(self):
        t = test.APIC_TENANT
        c = test.APIC_CONTRACT
        f = test.APIC_FILTER
        e = test.APIC_ENTRY
        s = test.APIC_SUBJECT
        fa_in = test.APIC_FILTER + '_in'
        fa_out = test.APIC_FILTER + '_out'
        self.apic.vzRsFiltAtt__Out.delete(t, c, s, fa_out)
        self.apic.vzOutTerm.delete(t, c, s)
        self.apic.vzRsFiltAtt__In.delete(t, c, s, fa_in)
        self.apic.vzInTerm.delete(t, c, s)
        self.apic.vzSubj.delete(t, c, s)
        self.apic.vzBrCP.delete(t, c)
        self.apic.vzEntry.delete(t, f, e)
        self.apic.vzFilter.delete(t, f)
        self.apic.fvTenant.delete(t)

    def test_contracts_filters_subjects_in_out(self):
        self.clean_up_contracts_filters_subjects_etc()
        self.addCleanup(self.clean_up_contracts_filters_subjects_etc)

        tenant = test.APIC_TENANT
        self.apic.fvTenant.create(tenant)
        new_tenant = self.apic.fvTenant.get(tenant)
        self.assertEqual(new_tenant['name'], tenant)
        LOG.debug(new_tenant['dn'])

        filter_x = test.APIC_FILTER
        self.apic.vzFilter.create(tenant, filter_x)
        new_filter_x = self.apic.vzFilter.get(tenant, filter_x)
        self.assertEqual(new_filter_x['name'], filter_x)
        LOG.debug(new_filter_x['dn'])

        entry = test.APIC_ENTRY
        self.apic.vzEntry.create(tenant, filter_x, entry,
                                 prot='6', dFromPort='10', dToPort='10')
        new_entry = self.apic.vzEntry.get(tenant, filter_x, entry)
        self.assertEqual(new_entry['name'], entry)
        LOG.debug(new_entry['dn'])

        contract = test.APIC_CONTRACT
        self.apic.vzBrCP.create(tenant, contract, scope='tenant')
        new_contract = self.apic.vzBrCP.get(tenant, contract)
        self.assertEqual(new_contract['name'], contract)
        LOG.debug(new_contract['dn'])

        subject = test.APIC_SUBJECT
        self.apic.vzSubj.create(tenant, contract, subject)
        new_subject = self.apic.vzSubj.get(tenant, contract, subject)
        self.assertEqual(new_subject['name'], subject)
        LOG.debug(new_subject['dn'])

        self.apic.vzInTerm.create(tenant, contract, subject)
        interm = self.apic.vzInTerm.get(tenant, contract, subject)
        LOG.debug(interm['dn'])

        fatt_in = test.APIC_FILTER + '_in'
        self.apic.vzRsFiltAtt__In.create(tenant, contract, subject, filter_x)
        new_fatt_in = self.apic.vzRsFiltAtt__In.get(tenant, contract,
                                                    subject, filter_x)
        LOG.debug(new_fatt_in['dn'])

        self.apic.vzOutTerm.create(tenant, contract, subject)
        outterm = self.apic.vzOutTerm.get(tenant, contract, subject)
        LOG.debug(outterm['dn'])

        fatt_out = test.APIC_FILTER + '_out'
        self.apic.vzRsFiltAtt__Out.create(tenant, contract, subject, filter_x)
        new_fatt_out = self.apic.vzRsFiltAtt__Out.get(tenant, contract,
                                                      subject, filter_x)
        LOG.debug(new_fatt_out['dn'])

    def test_contracts_filters_subjects_in_out_summary(self):
        self.clean_up_contracts_filters_subjects_etc()
        self.addCleanup(self.clean_up_contracts_filters_subjects_etc)

        tenant = test.APIC_TENANT
        filter_x = test.APIC_FILTER
        entry = test.APIC_ENTRY
        contract = test.APIC_CONTRACT
        subject = test.APIC_SUBJECT

        # tenant
        self.apic.fvTenant.create(tenant)
        # filter
        self.apic.vzFilter.create(tenant, filter_x)
        # entry
        self.apic.vzEntry.create(tenant, filter_x, entry,
                                 prot='6', dFromPort='10', dToPort='10')
        # contract
        self.apic.vzBrCP.create(tenant, contract)
        # subject
        self.apic.vzSubj.create(tenant, contract, subject)
        # input terminal
        self.apic.vzInTerm.create(tenant, contract, subject)
        # associate filer with input terminal
        self.apic.vzRsFiltAtt__In.create(tenant, contract, subject, filter_x)
        # output terminal
        self.apic.vzOutTerm.create(tenant, contract, subject)
        # associate filter with output terminal
        self.apic.vzRsFiltAtt__Out.create(tenant, contract, subject, filter_x)
