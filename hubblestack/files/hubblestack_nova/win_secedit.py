# -*- encoding: utf-8 -*-
"""
Windows secedit audit module
"""


import copy
import fnmatch
import logging
import hubblestack.utils
import hubblestack.utils.platform

try:
    import codecs
    import uuid
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

log = logging.getLogger(__name__)
__virtualname__ = 'win_secedit'


def __virtual__():
    if not hubblestack.utils.platform.is_windows() or not HAS_WINDOWS_MODULES:
        return False, 'This audit module only runs on windows'
    return True

def apply_labels(__data__, labels):
    """
    Filters out the tests whose label doesn't match the labels given when running audit and returns a new data structure with only labelled tests.
    """
    labelled_data = {}
    if labels:
        labelled_data[__virtualname__] = {}
        for topkey in ('blacklist', 'whitelist'):
            if topkey in __data__.get(__virtualname__, {}):
                labelled_test_cases=[]
                for test_case in __data__[__virtualname__].get(topkey, []):
                    # each test case is a dictionary with just one key-val pair. key=test name, val=test data, description etc
                    if isinstance(test_case, dict) and test_case:
                        test_case_body = test_case.get(next(iter(test_case)))
                        if set(labels).issubset(set(test_case_body.get('labels',[]))):
                            labelled_test_cases.append(test_case)
                labelled_data[__virtualname__][topkey]=labelled_test_cases
    else:
        labelled_data = __data__
    return labelled_data

def audit(data_list, tags, labels, debug=False, **kwargs):
    """
    Runs secedit on the local machine and audits the return data
    with the CIS yaml processed by __virtual__
    """
    __data__ = {}
    __secdata__ = _secedit_export()
    __sidaccounts__ = _get_account_sid()
    for profile, data in data_list:
        _merge_yaml(__data__, data, profile)
    __data__ = apply_labels(__data__, labels)
    __tags__ = _get_tags(__data__)
    __is_domain_controller__ = _is_domain_controller()
    if debug:
        log.debug('secedit audit __data__:')
        log.debug(__data__)
        log.debug('secedit audit __tags__:')
        log.debug(__tags__)

    ret = {'Success': [], 'Failure': [], 'Controlled': []}
    for tag in __tags__:
        if fnmatch.fnmatch(tag, tags):
            for tag_data in __tags__[tag]:
                if 'control' in tag_data:
                    ret['Controlled'].append(tag_data)
                    continue
                name = tag_data['name']
                audit_type = tag_data['type']
                output = tag_data['match_output'].lower()
                run_on_dc = tag_data.get('run_on_dc', True)
                run_on_member_server = tag_data.get('run_on_member_server', True)
                if __is_domain_controller__ and not run_on_dc:
                    continue
                if not __is_domain_controller__ and not run_on_member_server:
                    continue

                # Blacklisted audit (do not include)
                if audit_type == 'blacklist':
                    if 'no one' in output:
                        if name in __secdata__:
                            tag_data['failure_reason'] = "No value/account should be configured " \
                                                         "under '{0}', but atleast one value/account" \
                                                         " is configured on the system.".format(name)
                            ret['Failure'].append(tag_data)
                        else:
                            ret['Success'].append(tag_data)
                    elif name in __secdata__:
                        if secret := _translate_value_type(
                            __secdata__[name],
                            tag_data['value_type'],
                            tag_data['match_output'],
                        ):
                            tag_data['failure_reason'] = "Value of the key '{0}' is configured to a " \
                                                         "blacklisted value '{1}({2})'" \
                                                         .format(name,
                                                                 tag_data['match_output'],
                                                                 tag_data['value_type'])
                            ret['Failure'].append(tag_data)
                        else:
                            ret['Success'].append(tag_data)

                # Whitelisted audit (must include)
                if audit_type == 'whitelist':
                    if name in __secdata__:
                        sec_value = __secdata__[name]
                        tag_data['found_value'] = sec_value
                        if 'MACHINE\\' in name:
                            match_output = _reg_value_translator(tag_data['match_output'])
                        else:
                            match_output = tag_data['match_output']
                        if ',' in sec_value and '\\' in sec_value:
                            sec_value = sec_value.split(',')
                            match_output = match_output.split(',')
                        if 'account' in tag_data['value_type']:
                            secret = _translate_value_type(sec_value, tag_data['value_type'], match_output, __sidaccounts__)
                        else:
                            secret = _translate_value_type(sec_value, tag_data['value_type'], match_output)
                        if secret:
                            ret['Success'].append(tag_data)
                        else:
                            tag_data['failure_reason'] = "Value of the key '{0}' is configured to" \
                                                         " invalid value '{1}'. It should be set to" \
                                                         " '{2}({3})'".format(name,
                                                                             sec_value,
                                                                             match_output,
                                                                             tag_data['value_type'])
                            ret['Failure'].append(tag_data)
                    else:
                        log.error(f'name {name} was not in __secdata__')
                        tag_data['failure_reason'] = "Value of the key '{0}' could not be found in" \
                                                     " the registry. It should be set to '{1}({2})'" \
                                                     .format(name,
                                                             tag_data['match_output'],
                                                             tag_data['value_type'])
                        ret['Failure'].append(tag_data)

    return ret


def _merge_yaml(ret, data, profile=None):
    """
    Merge two yaml dicts together at the secedit:blacklist and
    secedit:whitelist level
    """
    if __virtualname__ not in ret:
        ret[__virtualname__] = {}
    for topkey in ('blacklist', 'whitelist'):
        if topkey in data.get(__virtualname__, {}):
            if topkey not in ret[__virtualname__]:
                ret[__virtualname__][topkey] = []
            for key, val in data[__virtualname__][topkey].items():
                if profile and isinstance(val, dict):
                    val['nova_profile'] = profile
                ret[__virtualname__][topkey].append({key: val})
    return ret


def _get_tags(data):
    """
    Retrieve all the tags for this distro from the yaml
    """
    ret = {}
    distro = __grains__.get('osfullname')
    for toplist, toplevel in data.get(__virtualname__, {}).items():
        # secedit:whitelist
        for audit_dict in toplevel:
            for audit_id, audit_data in audit_dict.items():
                # secedit:whitelist:PasswordComplexity
                tags_dict = audit_data.get('data', {})
                # secedit:whitelist:PasswordComplexity:data
                tags = None
                for osfinger in tags_dict:
                    if osfinger == '*':
                        continue
                    osfinger_list = [finger.strip() for finger in osfinger.split(',')]
                    for osfinger_glob in osfinger_list:
                        if fnmatch.fnmatch(distro, osfinger_glob):
                            tags = tags_dict.get(osfinger)
                            break
                    if tags is not None:
                        break
                # If we didn't find a match, check for a '*'
                if tags is None:
                    tags = tags_dict.get('*', [])
                # secedit:whitelist:PasswordComplexity:data:Server 2012
                if isinstance(tags, dict):
                    # malformed yaml, convert to list of dicts
                    tmp = [{name: tag} for name, tag in tags.items()]
                    tags = tmp
                for item in tags:
                    for name, tag in item.items():
                        tag_data = {}
                        # Whitelist could have a dictionary, not a string
                        if isinstance(tag, dict):
                            tag_data = copy.deepcopy(tag)
                            tag = tag_data.pop('tag')
                        if tag not in ret:
                            ret[tag] = []
                        formatted_data = {'name': name,
                                          'tag': tag,
                                          'module': 'win_secedit',
                                          'type': toplist}
                        formatted_data |= tag_data
                        formatted_data.update(audit_data)
                        formatted_data.pop('data')
                        ret[tag].append(formatted_data)
    return ret


def _secedit_export():
    """Helper function that will create(dump) a secedit inf file.  You can
    specify the location of the file and the file will persist, or let the
    function create it and the file will be deleted on completion.  Should
    only be called once."""
    dump = f"C:\ProgramData\{uuid.uuid4()}.inf"
    try:
        if ret := __mods__['cmd.run']('secedit /export /cfg {0}'.format(dump)):
            secedit_ret = _secedit_import(dump)
            ret = __mods__['file.remove'](dump)
            return secedit_ret
    except Exception:
        log.debug('Error occurred while trying to get / export secedit data')
        return False, None


def _secedit_import(inf_file):
    """This function takes the inf file that SecEdit dumps
    and returns a dictionary"""
    sec_return = {}
    with codecs.open(inf_file, 'r', encoding='utf-16') as f:
        for line in f:
            line = str(line).replace('\r\n', '')
            if not line.startswith('[') and not line.startswith('Unicode'):
                k, v = line.split(' = ') if ' = ' in line else line.split('=')
                sec_return[k] = v
    return sec_return


def _get_account_sid():
    """This helper function will get all the users and groups on the computer
    and return a dictionary"""
    win32 = __mods__['cmd.run']('Get-WmiObject win32_useraccount -Filter "localaccount=\'True\'"'
                                ' | Format-List -Property Name, SID', shell='powershell',
                                python_shell=True)
    win32 += '\n'
    win32 += __mods__['cmd.run']('Get-WmiObject win32_group -Filter "localaccount=\'True\'" | '
                                 'Format-List -Property Name, SID', shell='powershell',
                                 python_shell=True)
    if win32:

        dict_return = {}
        lines = win32.split('\n')
        lines = [_f for _f in lines if _f]
        if 'local:' in lines:
            lines.remove('local:')
        for line in lines:
            line = line.strip()
            if line != '' and ' : ' in line:
                k, v = line.split(' : ')
                if k.lower() == 'name':
                    key = v
                else:
                    dict_return[key] = v
        if dict_return:
            if 'LOCAL SERVICE' not in dict_return:
                dict_return['LOCAL SERVICE'] = 'S-1-5-19'
            if 'NETWORK SERVICE' not in dict_return:
                dict_return['NETWORK SERVICE'] = 'S-1-5-20'
            if 'SERVICE' not in dict_return:
                dict_return['SERVICE'] = 'S-1-5-6'
            return dict_return
        else:
            log.debug('Error parsing the data returned from powershell')
            return False
    else:
        log.debug('error occurred while trying to run powershell '
                  'get-wmiobject command')
        return False


def _translate_value_type(current, value, evaluator, __sidaccounts__=False):
    """This will take a value type and convert it to what it needs to do.
    Under the covers you have conversion for more, less, and equal"""
    value = value.lower()
    if 'more' in value:
        if ',' in evaluator:
            evaluator = evaluator.split(',')[1]
        if ',' in current:
            current = current.split(',')[1]
        if '"' in current:
            current = current.replace('"', '')
        if '"' in evaluator:
            evaluator = evaluator.replace('"', '')
        return int(current) >= int(evaluator)
    elif 'less' in value:
        if ',' in evaluator:
            evaluator = evaluator.split(',')[1]
        if ',' in current:
            current = current.split(',')[1]
        if '"' in current:
            current = current.replace('"', '')
        if '"' in evaluator:
            evaluator = evaluator.replace('"', '')
        return int(current) <= int(evaluator) and current != '0'
    elif 'equal' in value:
        if ',' not in evaluator and type(evaluator) != list:
            tmp_evaluator = _evaluator_translator(evaluator)
            if tmp_evaluator != 'undefined':
                evaluator = tmp_evaluator
        if type(current) == list:
            ret_final = []
            for item in current:
                item = item.lower()
                if item in evaluator:
                    ret_final.append(True)
                else:
                    ret_final.append(False)
            return False not in ret_final
        return current.lower() == evaluator
    elif 'account_contains' in value:  # Require an account to be present, but not exclusively.
        if "*S-" not in evaluator:
            evaluator = _account_audit(evaluator, __sidaccounts__)
        evaluator_list = evaluator.split(',')
        current_list = current.split(',')
        return all(list_item in current_list for list_item in evaluator_list)
    elif 'contains' in value:
        if type(evaluator) != list:
            evaluator = evaluator.split(',')
            if type(current) != list:
                current = current.lower().split(',')
            ret_final = []
            for item in evaluator:
                if item in current:
                    ret_final.append(True)
                else:
                    ret_final.append(False)
            return False not in ret_final
    elif 'account' in value:
        if "*S-" not in evaluator:
            evaluator = _account_audit(evaluator, __sidaccounts__)
        evaluator_list = evaluator.split(',')
        current_list = current.split(',')
        list_match = False
        for list_item in evaluator_list:
            if list_item in current_list:
                list_match = True
            else:
                list_match = False
                break
        if not list_match:
            return False
        for list_item in current_list:
            if list_item in evaluator_list:
                list_match = True
            else:
                list_match = False
                break
        return bool(list_match)
    elif 'configured' in value:
        if current == '':
            return False
        elif current.lower().find(evaluator) != -1:
            return True
        else:
            return False
    else:
        return 'Undefined'


def _evaluator_translator(input_string):
    """This helper function takes words from the CIS yaml and replaces
    them with what you actually find in the secedit dump"""
    if type(input_string) == str:
        input_string = input_string.replace(' ', '').lower()

    if 'enabled' in input_string:
        return '1'
    elif 'disabled' in input_string:
        return '0'
    elif 'success' in input_string:
        return '1'
    elif 'failure' in input_string:
        return '2'
    elif input_string in ['success,failure', 'failure,success']:
        return '3'
    elif input_string in ['0', '1', '2', '3']:
        return input_string
    else:
        log.debug('error translating evaluator from enabled/disabled or success/failure.'
                  '  Could have received incorrect string')
        return 'undefined'


def _account_audit(current, __sidaccounts__):
    """This helper function takes the account names from the cis yaml and
    replaces them with the account SID that you find in the secedit dump"""
    user_list = current.split(', ')
    ret_string = ''
    if __sidaccounts__:
        for usr in user_list:
            if usr == 'Guest':
                if ret_string:
                    ret_string += f',{usr}'
                else:
                    ret_string = usr
            if usr in __sidaccounts__:
                if not ret_string:
                    ret_string = f'*{__sidaccounts__[usr]}'
                else:
                    ret_string += f',*{__sidaccounts__[usr]}'
        return ret_string
    else:
        log.debug('getting the SIDs for each account failed')
        return False


def _reg_value_translator(input_string):
    input_string = input_string.lower()
    if input_string == 'administrators':
        return '1,"0"'
    elif input_string == 'defined (blank)':
        return '7,'
    elif input_string in ['disabled', 'automatically deny elevation requests']:
        return '4,0'
    elif input_string in [
        'enabled',
        'accept if provided by client',
        'classic - local users authenticate as themselves',
        'negotiate signing',
    ]:
        return '4,1'
    elif input_string == 'lock workstation':
        return '1,"1"'
    elif input_string == 'prompt for consent on the secure desktop':
        return '4,2'
    elif (
        input_string
        == 'rc4_hmac_md5, aes128_hmac_sha1, aes256_hmac_sha1, future encryption types'
    ):
        return '4,2147483644'
    elif (
        input_string
        == 'require ntlmv2 session security, require 128-bit encryption'
    ):
        return '4,537395200'
    elif input_string == 'send ntlmv2 response only. refuse lm & ntlm':
        return '4,5'
    elif input_string == 'users cant add or log on with microsoft accounts':
        return '4,3'
    else:
        return input_string


def _is_domain_controller():
    ret = __mods__['reg.read_value'](hive="HKLM",
                                     key=r"SYSTEM\CurrentControlSet\Control\ProductOptions",
                                     vname="ProductType")
    return ret['vdata'] == "LanmanNT"
