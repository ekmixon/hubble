# -*- coding: utf-8 -*-
"""
Custom grains around fqdn
"""
import hubblestack.grains.core
import hubblestack.modules.cmdmod
import hubblestack.utils.platform

__mods__ = {'cmd.run': hubblestack.modules.cmdmod._run_quiet,
            'cmd.run_all': hubblestack.modules.cmdmod.run_all}


def fqdn():
    """
    Generate a secondary fqdn with `hostname --fqdn` since socket.getfqdn()
    appears to be susceptible to issues with DNS
    """
    grains = {}
    local_fqdn = (
        None
        if hubblestack.utils.platform.is_windows()
        else __mods__['cmd.run']('hostname --fqdn')
    )

    if local_fqdn and 'hostname: ' not in local_fqdn:
        grains['local_fqdn'] = local_fqdn
    return grains


def dest_ip():
    """
    Generate a best-guess at the IP on the interface that is the default
    gateway for the host. This is because the current methods can result in
    various IPs due to round robin DNS.
    """
    interfaces = hubblestack.grains.core.ip4_interfaces()['ip4_interfaces']
    try:
        ret = __mods__['cmd.run_all']('ip route show to 0/0')
        if ret['retcode'] == 0:
            interface = None
            try:
                interface = ret['stdout'].split(' ')[4]
            except (AttributeError, KeyError, IndexError):
                pass
            if interface and interface in interfaces and interfaces[interface]:
                for ip_addr in interfaces[interface]:
                    if ip_addr != '127.0.0.1':
                        return {'local_ip4': ip_addr}
    except Exception:
        pass

    return _find_addr(interfaces)


def _find_addr(interfaces):
    """ Helper function that looks for ip addresses that are not empty, l0 or docker0 """
    # Fallback to "best guess"
    filtered_interfaces = {
        interface: ips
        for interface, ips in interfaces.items()
        if ips and interface not in ('lo', 'docker0')
    }

    # Use eth0 if present
    if 'eth0' in filtered_interfaces:
        for ip_addr in filtered_interfaces['eth0']:
            if ip_addr != '127.0.0.1':
                return {'local_ip4': ip_addr}
    # Use .*0 if present
    for interface, ips in filtered_interfaces.items():
        if '0' in interface:
            for ip_addr in ips:
                if ip_addr != '127.0.0.1':
                    return {'local_ip4': ip_addr}
    # Use whatever isn't 127.0.0.1
    for ips in filtered_interfaces.values():
        for ip_addr in ips:
            if ip_addr != '127.0.0.1':
                return {'local_ip4': ip_addr}
    # Give up
    return {'local_ip4', ''}
