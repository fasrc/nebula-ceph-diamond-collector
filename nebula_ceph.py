#!/usr/bin/python

"""
nebula_ceph.py
Extend Diamond Ceph collector to gather metrics only for Opennebula VM disks
"""


import glob
import os
import socket
import subprocess
import shlex
import xml.etree.ElementTree
import re

# import the ceph diamond collector
import ceph

PID_CCTID_REGEX = "ceph-([0-9]*)\.([0-9]*).*"
RBD_STAT_RE = "^librbd.*(one(?:-[0-9]*){1,3})"
METRIC_CHARS_RE = "[a-zA-Z0-9_-]"
METRIC_NAME_MAX_LEN = 255


class NebulaCephCollector(ceph.CephCollector):

    def get_default_config_help(self):
        config_help = super(NebulaCephCollector,
                            self).get_default_config_help()
        config_help.update({
            'pid_cctid_regex':
                'Matching group regex to select PID and CCTID from socket'
                ' name. Defaults to "%s"' % PID_CCTID_REGEX,
            'prefix_variable':
                'OpenNebula VM Template variable to customize diamond prefix.'
                ' Defaults to "DIAMOND_PREFIX"',
            'default_prefix':
                'Default prefix to add if not overriding. Defaults to'
                ' "nebulaceph"',
            'qemu_pid_path':
                'The location of the qemu pid files. Defaults to'
                ' "/var/run/libvirt/qemu"',
        })
        return config_help

    def get_default_config(self):
        """
        Returns the default collector settings
        """
        config = super(NebulaCephCollector, self).get_default_config()
        config.update({
            'pid_cctid_regex': PID_CCTID_REGEX,
            'prefix_variable': 'DIAMOND_PREFIX',
            'default_prefix': 'nebulaceph',
            'qemu_pid_path': '/var/run/libvirt/qemu',
        })
        return config

    def _get_vm_pid(self, vmid):
        """Return the qemu pid for an opennebula vm
        """
        qemu_pid_file = '%s/one-%s.pid' % (self.config['qemu_pid_path'], vmid)
        if os.path.isfile(qemu_pid_file):
            pid = open(qemu_pid_file).read()
            return pid

    def _validate_metric_name(self, string):
        validated_string = ''
        for char in string[:METRIC_NAME_MAX_LEN-1]:
            if re.search(METRIC_CHARS_RE, char):
                validated_string += char
            else:
                validated_string += '_'
        return validated_string

    def _get_nebula_vms(self):
        """Return a hash of OpenNebula vms with pid and diamond_prefix
        """
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        args = shlex.split('onevm list -x')
        vm_xml_list = subprocess.Popen(args, stdout=subprocess.PIPE)
        vm_xml_arr = vm_xml_list.stdout.readlines()
        vm_xml_string = ''.join([line.strip("\n") for line in vm_xml_arr])
        vm_xml_etree = xml.etree.ElementTree.fromstring(vm_xml_string)
        vm_hash = {}
        for vm in vm_xml_etree.findall("VM"):
            vm_hostname_element = vm.find("*//HOSTNAME")
            if vm_hostname_element is None:
                # this vm is undeployed or pending, so skip it
                continue
            vm_hostname = vm_hostname_element.text
            if vm_hostname not in [hostname, fqdn]:
                continue
            vm_id = vm.find("ID").text
            pid = self._get_vm_pid(vm_id)
            if not pid:
                continue
            vm_name = self._validate_metric_name(vm.find("NAME").text)
            vm_diamond_prefix_element = vm.find("*//DIAMOND_PREFIX")
            if vm_diamond_prefix_element is None:
                # no diamond prefix in template, so set to default
                vm_diamond_prefix = self.config['default_prefix']
            else:
                vm_diamond_prefix = self.validate_metric_name(
                    vm_diamond_prefix_element.text)
            vm_hash[vm_id] = dict(diamond_prefix=vm_diamond_prefix,
                                  pid=pid, name=vm_name)
        return vm_hash

    def _get_socket_paths(self):
        """Return an array of hashes for ceph sockets with path, pid and cctid
        """
        socket_pattern = os.path.join(self.config['socket_path'],
                                      (self.config['socket_prefix'] +
                                       '*.' + self.config['socket_ext']))
        pid_cctid_pattern = r'%s/%s' % (self.config['socket_path'],
                                        self.config['pid_cctid_regex'])
        path_arr = []
        for path in glob.glob(socket_pattern):
            pid_cctid_match = re.match(pid_cctid_pattern, path)
            if pid_cctid_match is not None:
                pid, cctid = pid_cctid_match.groups()
                path_arr.append(dict(pid=pid, cctid=cctid, path=path))
        return path_arr

    def _get_rbd_device_from_stat(self, stat):
        rbd_device = re.match(RBD_STAT_RE, stat)
        if rbd_device:
            return rbd_device.groups()[0]

    def _publish_stats(self, counter_prefix, stats, instance):
        """Given a stats dictionary from _get_stats_from_socket,
        publish the individual values.
        """
        for stat_name, stat_value in ceph.flatten_dictionary(
            stats,
            prefix=counter_prefix,
        ):
            self.publish_gauge(stat_name, stat_value, instance=instance)

    def collect(self):
        """
        Collect stats for OpenNebula vms rbd devices
        """
        socket_path_arr = self._get_socket_paths()
        for vmid, vm_hash in self._get_nebula_vms().items():
            self.log.debug('checking vm %s', vmid)
            sockets = [socket for socket in socket_path_arr if
                       socket['pid'] == vm_hash['pid']]
            for socket_hash in sockets:
                self.log.debug('found socket')
                stats = self._get_stats_from_socket(socket_hash['path'])
                for stat in stats:
                    device = self._get_rbd_device_from_stat(stat)
                    if not device:
                        continue
                    self.log.debug('found device %s' % device)
                    prefix = "%s.%s.%s" % (vm_hash['diamond_prefix'],
                                              vm_hash['name'], device)
                    self._publish_stats(counter_prefix=prefix,
                                        stats=stats[stat], instance=vmid)
