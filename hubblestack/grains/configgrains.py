# -*- coding: utf-8 -*-
"""
Custom config-defined grains module

Allow users to collect a list of config directives and set them as custom
grains.  The list should be defined under the `config_to_grains` key.

The `config_grains` value should be a list of dictionaries. Each dictionary
should have a single key which will be set as the grain name. The dictionary's
value will be the grain's value.

hubblestack:
  returner:
    splunk:
      - token: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        indexer: splunk-indexer.domain.tld
        index: hubble
        sourcetype_nova: hubble_audit
config_to_grains:
  - splunkindex: "hubblestack:returner:splunk:0:index"
"""

import hubblestack.modules.config

hubblestack.modules.config.__pillar__ = {}
hubblestack.modules.config.__grains__ = {}

__mods__ = {'config.get': hubblestack.modules.config.get}


def configgrains():
    """
    Given a list of config values, create custom grains with custom names.
    The list comes from config.

    Example:

    config_to_grains:
      - splunkindex: "hubblestack:returner:splunk:0:index"
    """
    grains = {}
    hubblestack.modules.config.__opts__ = __opts__

    grains_to_make = __mods__['config.get']('config_to_grains', default=[])
    for grain in grains_to_make:
        for grain_key, grain_value in grain.items():
            if grain_value := __mods__['config.get'](
                grain_value, default=None
            ):
                grains[grain_key] = grain_value
    return grains
