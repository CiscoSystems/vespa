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

from oslo.config import cfg


vespa_opts = [
    cfg.StrOpt('ifc_host',
               help=_("Host name or IP Address of the IFC controller")),
    cfg.StrOpt('ifc_username',
               help=_("Username for the IFC controller")),
    cfg.StrOpt('ifc_password',
               help=_("Password for the IFC controller")),
    cfg.StrOpt('ifc_port',
               help=_("Communication port for the IFC controller")),
]


cfg.CONF.register_opts(vespa_opts, "ml2_vespa")


class ML2MechVespaConfig(object):
    """ML2 Mechanism Driver Vespa Configuration class."""
    host_pools = {}

    def __init__(self):
        self._create_host_pool_dictionary()

    def _create_host_pool_dictionary(self):
        multi_parser = cfg.MultiConfigParser()
        read_ok = multi_parser.read(cfg.CONF.config_file)

        if len(read_ok) != len(cfg.CONF.config_file):
            raise cfg.Error(_("Some config files were not parsed properly"))

        for parsed_file in multi_parser.parsed:
            for parsed_item in parsed_file.keys():
                pool, sep, pool_id = parsed_item.partition(':')
                if pool.lower() == 'host_pool':
                    self.host_pools[pool_id] = {}
                    self.host_pools[pool_id]['hosts'] = \
                    parsed_file[parsed_item]['hosts'][0].split(',')

                    self.host_pools[pool_id]['switch_ip'] = \
                    parsed_file[parsed_item]['switch'][0]

                    self.host_pools[pool_id]['port_id'] = \
                    parsed_file[parsed_item]['port'][0]
