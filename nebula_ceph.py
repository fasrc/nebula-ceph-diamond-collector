#!/usr/bin/python

"""
nebula_ceph.py
Extend Diamond Ceph collector to gather metrics only for Opennebula VM disks
"""


import glob
import sys
import os
import socket
import subprocess
import shlex
import xml.etree.ElementTree
import re

import diamond.collector

# import the ceph diamond collector
import ceph

PID_CCTID_REGEX = "ceph-([0-9]*)\.([0-9]*).*"

class NebulaCephCollector(ceph.CephCollector):

    def get_default_config_help(self):
        config_help = super(NebulaCephCollector, self).get_default_config_help()
        config_help.update({
            'pid_cctid_regex': 'Matching group regex to select PID and CCTID from socket name.'
                            ' Defaults to %s' % PID_CCTID_REGEX,
            'nebula_template_prefix_variable': 'OpenNebula VM Template variable to'
                            ' customize diamond prefix. Defaults to DIAMOND_PREFIX',
            'default_prefix': 'Default prefix to add if not overriding. Defaults to "vms".'
        })
        return config_help

    def get_default_config(self):
        """
        Returns the default collector settings
        """
        config = super(NebulaCephCollector, self).get_default_config()
        config.update({
            'pid_cctid_regex': PID_CCTID_REGEX,
            'nebula_template_prefix_variable': 'DIAMOND_PREFIX',
            'default_prefix': 'vms'
        })
        return config

    def _get_vm_pid(self, vmid):
        """Return the qemu pid for an opennebula vm
        """
        try:
            pid = open('/var/run/libvirt/qemu/one-%s.pid' % vmid).read()
            return pid
        except:
            pass

    def _get_nebula_vms(self):
        """Return a hash of OpenNebula vms with pid and diamond_prefix
        """
        hostname = socket.gethostname()
        args = shlex.split('onevm list -x')
        vm_xml_arr = subprocess.Popen(args,stdout=subprocess.PIPE).stdout.readlines()
        vm_xml_string = ''.join([line.strip("\n") for line in vm_xml_arr])
        vm_xml_etree = xml.etree.ElementTree.fromstring(vm_xml_string)
        vm_hash = {}
        for vm in vm_xml_etree.findall("VM"):
            vm_id = vm.find("ID").text
            vm_hostname = vm.find("*//HOSTNAME").text
            if vm_hostname == hostname:
                try:
                    vm_diamond_prefix = vm.find("*//DIAMOND_PREFIX").text
                except:
                    vm_diamond_prefix = self.config['default_prefix']
                vm_hash[vm_id] = dict(
                                    diamond_prefix = vm_diamond_prefix,
                                    pid = self._get_vm_pid(vm_id)
                                )
        return vm_hash

    def _get_socket_paths(self):
        """Return an array of hashes for ceph sockets with path, pid and cctid
        """
        socket_pattern = os.path.join(self.config['socket_path'],
                                      (self.config['socket_prefix'] +
                                       '*.' + self.config['socket_ext']))
        pid_cctid_pattern = r'%s/%s' % (self.config['socket_path'],self.config['pid_cctid_regex'])
        path_arr = []
        for path in glob.glob(socket_pattern):
            try:
                pid, cctid = re.match(pid_cctid_pattern,path).groups()
                path_arr.append(dict(pid= pid, cctid=cctid, path=path))
            except:
                pass
        return path_arr

    def collect(self):
        """
        Collect stats for OpenNebula vms rbd devices
        """
        socket_path_arr = self._get_socket_paths()
        for vmid, vm_hash in self._get_nebula_vms().items():
            self.log.debug('checking vm %s', vmid)
            sockets = [socket for socket in socket_path_arr if socket['pid']==vm_hash['pid']]
            for socket_hash in sockets:
                prefix = "%s.%s.%s" % (vm_hash['diamond_prefix'], vmid, socket_hash['cctid'])
                stats = self._get_stats_from_socket(socket_hash['path'])
                self._publish_stats(prefix, stats)
        return
