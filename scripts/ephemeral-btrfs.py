#!/usr/bin/env python

from __future__ import print_function
from os import path
from subprocess import call
from sys import exit, stderr
from urllib2 import urlopen

# Helpers
def warning(*objs):
    print('WARNING: ', *objs, file=stderr)

def error(*objs):
    print('ERROR: ', *objs, file=stderr)

CMD_MOUNT = 'mount -o {0} {1} /usr/local/wrf'
MOUNT_OPTS = 'defaults,noatime'
MDADM_DEVICE_NAME = '/dev/md0'

blockDevices = urlopen('http://169.254.169.254/latest/meta-data/block-device-mapping/').readlines()

ephemeralDevices = []
for device in blockDevices:
    if 'ephemeral' in device:
        ephemeralDevice = urlopen('http://169.254.169.254/latest/meta-data/block-device-mapping/' + device.strip()).read()
        devPath = path.realpath('/dev/' + ephemeralDevice)
        ephemeralDevices.append(devPath)

if not path.isfile('/sbin/mkfs.btrfs'):
    cmd = '/sbin/mkfs.btrfs -fKd raid0 {0}'.format(' '.join(ephemeralDevices))
    call(cmd.split())
    cmd = CMD_MOUNT.format(MOUNT_OPTS, ephemeralDevices[0])
    call(cmd.split())
else:
    if path.exists(MDADM_DEVICE_NAME):
        error(MDADM_DEVICE_NAME + ' already exists! Cancelling Ephemeral RAID0 Creation!')
        exit(1)
    cmd = 'mdadm --create --verbose --force {0} --level=stripe --raid-devices={1} {2}'.format(MDADM_DEVICE_NAME, len(ephemeralDevices), ' '.join(ephemeralDevices))
    call(cmd.split())
    cmd = '/sbin/mkfs.ext2 -E lazy_itable_init {0}'.format(MDADM_DEVICE_NAME)
    call(cmd.split())
    cmd = CMD_MOUNT.format(MOUNT_OPTS, MDADM_DEVICE_NAME)
    call(cmd.split())
