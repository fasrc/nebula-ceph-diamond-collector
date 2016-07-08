# nebula-ceph-diamond-collector

Diamond collectors for OpenNebula VM disks on Ceph

## Description

These collectors are intended to be used with diamond [diamond](https://github.com/python-diamond/Diamond) to ship stats to [graphite](http://graphite.wikidot.com/ "Graphite"). This collector allows to gather Ceph performance data for OpenNebula VMs disks on Ceph.


## NebulaCephCollector

This collector extends CephCollector from diamond and gathers metrics for OpenNebula VM disks on Ceph.

This queries OpenNebula frontend to gather vms on the current hypervisor and uses the qemu PIDs for those vms to selects Ceph admin sockets and gathers metrics for those RBD devices.

Metrics sent to graphite are of the form: 

    '<instance_prefix>.<vmid>.<diamond_prefix>.<vm name>.<rbd device name>.<metric name>'

(note that prefix is in addition to the global prefix already set in diamond)

## Usage

- install opennebula cli gem on the hypervisors
- setup credentials for the root user on the hypervisors to authenticate to the OpenNebula frontend (one_auth file)
- setup root's bashrc to export ONE_XMLRPC (with the url to the frontend), and ONE_AUTH (with a path to the one_auth file)

- setup ceph admin socket in ceph.conf (not on by default for ceph clients)
- configure pid_cctid_regex in diamond for this collector to match the format of the asok name in ceph.conf (this is for this collector to select PID and CCTID from the socket name; the first matching group should be pid and the second is cctid)
- also configure socket_path and socket_prefix and socket_ext if needed (see Diamond Ceph collector)

## Optional config

- nebula_template_prefix_variable - if needed to override for certain vms. This allows to set different diamond prefixes by using a onevm template variable
- default_prefix - this is the default prefix to be added in diamond; defaults to 'nebulaceph'
- optionally change diamond's instance_prefix, default is 'instances'
