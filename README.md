# nebula-ceph-diamond-collector

Diamond collector for OpenNebula VM disks on Ceph

## Description

This collector is intended to be used with [diamond](https://github.com/python-diamond/Diamond) to ship stats to [graphite](http://graphite.wikidot.com/)/[grafana](http://grafana.org/).

This collector allows to gather Ceph performance data for OpenNebula VMs disks on Ceph.


## NebulaCephCollector

This collector extends CephCollector from diamond and gathers metrics for
OpenNebula VM disks on Ceph.

This queries OpenNebula frontend to gather vms on the current hypervisor and
uses the qemu PIDs for those vms to selects Ceph admin sockets and gathers
metrics for those RBD devices.

Metrics sent to graphite are of the form: 

    <instance_prefix>.<vmid>.NebulaCephCollector.<diamond_prefix>.<vm name>.
    <rbd device name>.<metric name>

(note that instance_prefix is customized once per host (hypervisor) in diamond configuration, and diamond_prefix is customized per vm based on an opennebula vm template variable)

## Usage

### Prerequisites
- install opennebula-cli gem (or yum package opennebula) on the hypervisors
- setup one_auth file on the hypervisors with credentials to authenticate to the OpenNebula frontend
- setup ceph admin socket in ceph.conf on the hypervisors (this is not enabled by default for ceph clients, format like `admin_socket = /full/path/$cluster-$pid.$cctid.asok`)

### Configuration variables for this diamond collector
- one_xmlrpc: url to the frontend
- one_auth: path to the one_auth file
- pid_cctid_regex: regex to select PID and CCTID from the socket name; the first matching group should be pid and the second is cctid; must match the format of the asok name in ceph.conf
- socket_path, and socket_prefix/socket_ext if needed (see Diamond Ceph collector)

### Optional config

- nebula_template_prefix_variable - if needed to override diamond_prefix for certain vms. This allows to set different diamond prefixes by using a onevm template variable; this can allow to set different storage schemas in graphite for different vms (e.g., shorter retention for test vms)
- default_prefix - this is the default value for diamond_prefix; defaults to 'nebulaceph'
- optionally change diamond's instance_prefix, default in diamond is 'instances'
