# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013: Mirantis Inc.
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

import netaddr
import os
import subprocess
import time
import uuid

from rally.serverprovider import provider


class VirshProvider(provider.ProviderFactory):
    '''Creates VMs from prebuilt templates.
    config example:
        "vm_provider": {
            "name": "VirshProvider",
            "connection": "alex@performance-01",  # ssh connection to vms host
            "template_name": "stack-01-devstack-template",  # vm image template
        },
    '''

    def __init__(self, config):
        self._config = config

    def create_vms(self, image_uuid=None, type_id=None, amount=1):
        """Create VMs with chosen image.
        :param image_uuid: Indetificator of image
        :param amount: amount of required VMs
        Returns list of VMs uuids.
        """
        return [self.create_vm(str(uuid.uuid4())) for i in range(amount)]

    def create_vm(self, vm_name):
        '''Clones prebuilt VM template and starts it.'''

        virt_url = self._get_virt_connection_url(self._config['connection'])
        cmd = 'virt-clone --connect=%(url)s -o %(t)s -n %(n)s --auto-clone' % {
            't': self._config['template_name'],
            'n': vm_name,
            'url': virt_url
        }
        subprocess.check_call(cmd, shell=True)

        cmd = 'virsh --connect=%s start %s' % (virt_url, vm_name)
        subprocess.check_call(cmd, shell=True)

        return {
            'id': id,
            'name': vm_name,
            'ip': self._determine_vm_ip(vm_name),
        }

    def destroy_vms(self, vm_uuids):
        '''Destroy already created vms by vm_uuids.'''
        for vm in vm_uuids:
            self.destroy_vm(vm)

    def destroy_vm(self, vm):
        '''Destroy single vm and delete all allocated resources.'''
        print('Destroy VM %s' % vm['name'])
        vconnection = self._get_virt_connection_url(self._config['connection'])

        cmd = 'virsh --connect=%s destroy %s' % (vconnection, vm['name'])
        subprocess.check_call(cmd, shell=True)

        cmd = 'virsh --connect=%s undefine %s --remove-all-storage' % (
                vconnection, vm['name'])
        subprocess.check_call(cmd, shell=True)
        return True

    @staticmethod
    def _get_virt_connection_url(connection):
        '''Formats QEMU connection string from SSH url.'''
        return 'qemu+ssh://%s/system' % connection

    def _determine_vm_ip(self, vm_name):
        ssh_opt = '-o StrictHostKeyChecking=no'
        script_path = os.path.dirname(__file__) + '/virsh/get_domain_ip.sh'

        cmd = 'scp %(opts)s  %(name)s %(host)s:~/get_domain_ip.sh' % {
            'opts': ssh_opt,
            'name': script_path,
            'host': self._config['connection']
        }
        subprocess.check_call(cmd, shell=True)

        tries = 0
        ip = None
        while tries < 3 and not ip:
            cmd = 'ssh %(opts)s %(host)s ./get_domain_ip.sh %(name)s' % {
                'opts': ssh_opt,
                'host': self._config['connection'],
                'name': vm_name
            }
            out = subprocess.check_output(cmd, shell=True)
            try:
                ip = netaddr.IPAddress(out)
            except netaddr.core.AddrFormatError:
                ip = None
            tries += 1
            time.sleep(10)
        return str(ip)