#!/usr/bin/env python

# Standard Imports
from __future__ import print_function
from os import chmod, makedirs, path
from shutil import rmtree
from sys import exit, stderr
from time import sleep
from urllib2 import urlopen
import yaml

# Constants

TAG_PREFIX = 'wrf-ecs-label-{0}-'
DIR_INSTANCE = './instance/{0}/'
DEFAULT_AMI = 'ami-6ff4bd05'

# Helpers
def warning(*objs):
    print('WARNING: ', *objs, file=stderr)

def error(*objs):
    print('ERROR: ', *objs, file=stderr)

# Test required imports
try:
    from argparse import ArgumentParser
except ImportError:
    error('ArgumentParser is not available. Ensure Python interpreter is version 2.7+')
    exit(1)

try:
    from boto3.session import Session
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    error('Python boto3 AWS SDK is not installed. Try `pip install boto3` or `easy_install boto3` (preferrably in a virtual_env).')
    exit(1)

# Parse Args
parser = ArgumentParser(description="WRF MPI Docker Cluster Runner")
parser.add_argument("command", type=str, choices=['create', 'destroy'], help="what to do...")
parser.add_argument("where", type=str, choices=['aws'], help="where to create cluster")
#parser.add_argument("-L", "--label", type=str, default='default', help="The label to identify the instance of mini-project to create or interact with. Default label is 'default'")

global go_args
go_args = parser.parse_args()

global config
with open('config.yml', 'r') as yml:
    config = yaml.load(yml)

# General Functions

# Functions
def create():
    if go_args.where == 'aws':
        ecsConfig = config['ecs']
        tagPrefix = TAG_PREFIX.format(ecsConfig['label'])

        if ecsConfig['access-key'] == 'profile':
            ses = Session(profile_name=ecsConfig['profile'])
        else:
            ses = Session(aws_access_key_id=ecsConfig['access-key'], aws_secret_access_key=ecsConfig['secret-key'])
        ec2 = ses.resource('ec2')
        ecs = ses.resource('ecs')
        iam = ses.resource('iam')

        placement = ec2.create_placement_group(GroupName=tagPrefix + 'placement')
        subnet = ec2.Subnet(ecsConfig['subnet'])

def destroy():
    pass

commands = { 'create': create, 'destroy': destroy }

# Entry

if go_args.command in commands:
    commands[go_args.command]()
else:
    error("invalid command: '{0}' (choose from {1})".format(go_args.command, sorted(commands.keys())))
