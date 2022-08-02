"""
HubbleStack Domain Controller Grain.
CLI Usage - hubble grains.get domain_controller
Example Output - {u'domain_controller': True}
Author - Devansh Gupta (devagupt@adobe.com)
"""
import logging
import hubblestack.utils.win_reg
import hubblestack.utils.platform

__virtualname__ = "domain_controller"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Load domain controller grain
    """
    return (
        __virtualname__
        if hubblestack.utils.platform.is_windows()
        else (False, "The grain will only run on Windows systems")
    )


def get_domain_controller():
    reg_val = hubblestack.utils.win_reg.read_value(hive="HKLM", key=r"SYSTEM\CurrentControlSet\Control\ProductOptions", vname="ProductType")

    return {'domain_controller': reg_val['vdata'] == 'LanmanNT'}