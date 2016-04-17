#!/usr/bin/env python

# Standard Imports
from __future__ import print_function
from os import chmod, path
from shutil import rmtree
from sys import exit, stderr
from threading import Thread
from time import sleep
from urllib2 import urlopen
import yaml
import json

# Constants

TAG_PREFIX = 'wrf-ecs-{0}-'
DIR_INSTANCE = './instance/{0}/'
DEFAULT_AMI = 'ami-6ff4bd05'

ECS_ASSUME_ROLE_POLICY_DOC = '{"Version": "2012-10-17", "Statement": [{"Action": "sts:AssumeRole", "Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}}]}'
ECS_ROLE_POLICY_ARN = 'arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role'

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
    from boto3 import client
    from boto3.session import Session
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    error('Python boto3 AWS SDK is not installed. Try `pip install boto3` or `easy_install boto3` (preferrably in a virtual_env).')
    exit(1)

# Parse Args
parser = ArgumentParser(description="WRF MPI Docker Cluster Runner")
parser.add_argument("command", type=str, choices=['create_aws', 'destroy_aws'], help="what to do...")

global go_args
go_args = parser.parse_args()

global config
with open('config.yml', 'r') as yml:
    config = yaml.load(yml)

def get_aws_resources():
    r = { }
    
    # Configuration Parameters
    r['global'] = config['global']
    r['config'] = config['ecs']
    r['prefix'] = TAG_PREFIX.format(r['config']['label'])

    # Boto3 Session
    if r['config']['access-key'] == 'profile':
        r['session'] = Session(profile_name=r['config']['aws-profile'])
    else:
        r['session'] = Session(aws_access_key_id=r['config']['access-key'], aws_secret_access_key=r['config']['secret-key'])

    # Session Resources / Clients
    r['ec2'] = r['session'].resource('ec2')
    r['iam'] = r['session'].resource('iam')
    r['ecs'] = r['session'].client('ecs')

    # Individual Resources
    r['aws'] = { }

    # IAM Resources
    r['aws']['roles'] = list(r['iam'].roles.filter(PathPrefix='/' + r['prefix'] + 'roles'))
    r['aws']['instance_profiles'] = list(r['iam'].instance_profiles.filter(PathPrefix='/' + r['prefix'] + 'instance_profiles'))

    # EC2 Resources
    r['aws']['subnets'] = [r['ec2'].Subnet(r['config']['subnet'])]
    r['aws']['security_groups'] = list(r['ec2'].security_groups.filter(Filters=[{ 'Name': 'group-name', 'Values': [r['prefix'] + 'sg'] }]))
    r['aws']['placement_groups'] = list(r['ec2'].placement_groups.filter(Filters=[{ 'Name': 'group-name', 'Values': [r['prefix'] + 'placement'] }]))
    r['aws']['key_pairs'] = list(r['ec2'].key_pairs.filter(Filters=[{ 'Name': 'key-name', 'Values': [r['prefix'] + 'keypair']  }]))
    r['aws']['head_nodes'] = []
    r['aws']['worker_nodes'] = []

    # ECS Resources
    r['aws']['clusters'] = r['ecs'].describe_clusters(clusters=[r['prefix'] + 'cluster'])['clusters']

    # Count Resources
    r['resource_count'] = 0
    for resource in r['aws']:
        if resource == 'subnets':
            continue
        elif resource == 'clusters':
            for cluster in r['aws'][resource]:
                if cluster['status'] == 'ACTIVE':
                    r['resource_count'] += 1
        elif resource == 'head_nodes' or resource == 'worker_nodes':
            for instance in r['aws'][resource]:
                if instance.state['Name'] != 'terminated':
                    r['resource_count'] += 1
        else:
            r['resource_count'] += len(r['aws'][resource])

    return r

# Functions
def create_aws():
    #globalConfig = config['global']
    #ecsConfig = config['ecs']
    #tagPrefix = TAG_PREFIX.format(ecsConfig['label'])

    # AWS Session
    #if ecsConfig['access-key'] == 'profile':
    #    ses = Session(profile_name=ecsConfig['aws-profile'])
    #else:
    #    ses = Session(aws_access_key_id=ecsConfig['access-key'], aws_secret_access_key=ecsConfig['secret-key'])

    # Clients
    #ec2 = ses.resource('ec2')
    #iam = ses.resource('iam')
    #ecs = client('ecs')

    # Subnet
    #subnet = ec2.Subnet(ecsConfig['subnet'])

    r = get_aws_resources()

    if r['resource_count'] > 0:
        error('There are existing resources for the label: {0}. Run ./go.py destroy_aws to remove them.')
        exit(1)

    # IAM Role
    r['aws']['roles'] = []
    r['aws']['roles'][0] = r['iam'].create_role(Path='/' + r['prefix'] + 'role', AssumeRolePolicyDocument=ECS_ASSUME_ROLE_POLICY_DOC)
    r['aws']['roles'][0].attach_policy(PolicyArn=ECS_ROLE_POLICY_ARN)
        
    # IAM Instance Profile
    instance_profile = iam.create_instance_profile(Path='/' + tagPrefix + 'instance-profiles', InstanceProfileName=tagPrefix + 'instance-profile')
    instance_profile.add_role(RoleName=role.role_name)

    # Security Group
    sec_grp = subnet.vpc.create_security_group(GroupName=tagPrefix + 'sg', Description=tagPrefix + 'sg')
    sec_grp.authorize_ingress(IpPermissions=[
        { 'IpProtocol': '-1', 'FromPort': 0, 'ToPort': 65535, 'UserIdGroupPairs': [{ 'GroupId': sec_grp.group_id  }]  },
        { 'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{ 'CidrIp': ecsConfig['ssh-cidr'] }] }
    ])

    # Placement Group
    plcmnt_grp = ec2.create_placement_group(GroupName=tagPrefix + 'placement', Strategy='cluster')

    # ECS Cluster
    cluster = ecs.create_cluster(clusterName=tagPrefix + 'cluster')

    # Key Pair
    key_pair = ec2.create_key_pair(KeyName=tagPrefix + 'keypair')
    with open('./keys/' + key_pair.key_name + '.pem', 'w') as pem:
        pem.write(key_pair.key_material)
        chmod('./keys/' + key_pair.key_name + '.pem', 0600)

    # Head Node Network Interface
    head_network = ec2.create_network_interface(SubnetId=subnet.subnet_id, Groups=[sec_grp.group_id])

    # Worker Node User Data
    with open('./user-data/worker', 'r') as ud:
        worker_ud = ud.read()

    worker_nodes = ec2.create_instances(ImageId=ecsConfig['base-ami'], \
                       MinCount=globalConfig['nodes'], \
                       MaxCount=globalConfig['nodes'], \
                       KeyName=key_pair.key_name, \
                       UserData=worker_ud, \
                       InstanceType=ecsConfig['instance-type'], \
                       Placement={ 'GroupName': plcmnt_grp.group_name, 'Tenancy': ecsConfig['tenancy'] }, \
                       Monitoring={ 'Enabled': ecsConfig['monitoring'] }, \
                       SubnetId=subnet.subnet_id, \
                       InstanceInitiatedShutdownBehavior='terminate', \
                       NetworkInterfaces=[{ 'DeviceIndex': 0, 'SubnetId': subnet.subnet_id, 'Groups': [sec_grp.group_id], 'AssociatePublicIpAddress': True }], \
                       IamInstanceProfile={ 'Name': instance_profile.instance_profile_name })
    exit(0)

    # Head Node Block Devices
    head_block_devices = [
    {
        'DeviceName': '/dev/sdb',
        'Ebs': {
            'SnapshotId': ecsConfig['ebs-snapshot'],
            'VolumeSize': ecsConfig['ebs-size-gb'],
            'DeleteOnTermination': True,
            'Encrypted': False,
            'VolumeType': 'gp2'
        }
    }]

    if ecsConfig['ebs-iops'] > 0:
        head_block_devices[0]['Ebs']['VolumeType'] = 'io1'
        head_block_devices[0]['Ebs']['Iops'] = ecsConfig['ebs-iops']

    # Head Node User Data
    with open('./user-data/head', 'r') as ud:
        head_ud = ud.read()

    # Head Node Instance
'''
    head_node = ec2.create_instances(ImageId=ecsConfig['base-ami'], \
                    MinCount=1, \
                    MaxCount=1, \
                    KeyName=key_pair.key_name, \
                    UserData=head_ud, \
                    InstanceType=ecsConfig['instance-type'], \
                    Placement={ 'GroupName': plcmnt_grp.group_name, 'Tenancy': ecsConfig['tenancy'] }, \
                    BlockDeviceMapping=head_block_devices, \
                    Monitoring={ 'Enabled': ecsConfig['monitoring'] }, \
                    SubnetId=subnet.subnet_id, \
                    InstanceInitiatedShutdownBehavior='terminate', \
'''               

# Terminate Instance (Thread Target)
def terminate_instance(instance):
    if instance.state['Name'] != 'terminated':
        for network_interface in instance.network_interfaces:
            network_interface.detach()
            network_interface.delete()
        instance.terminate()
        instance.wait_until_terminated()

# Destroy AWS
def destroy_aws():
    r = get_aws_resources()

    # Resources Exist?
    if r['resource_count'] < 1:
        error('There are no resources for the label: ' + r['config']['label'])
        exit(1)

    # Terminate Instances
    threads = []

    for instance in r['aws']['worker_nodes']:
        t = Thread(target=terminate_instance, args=(instance,))
        t.daemon = True
        t.start()
        threads.append(t)
    
    for instance in r['aws']['head_nodes']:
        t = Thread(target=terminate_instance, args=(instance,))
        t.daemon = True
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # ECS Cluster
    for c in r['aws']['clusters']:
        r['ecs'].delete_cluster(cluster=c['clusterArn'])

    # All Other Resources
    for resource in r['aws']:
        if resource == 'head_nodes' or resource == 'worker_nodes' or resource == 'clusters':
            continue
        r['aws'][resource].delete()

commands = { 'create_aws': create_aws, 'destroy_aws': destroy_aws }

# Entry

if go_args.command in commands:
    commands[go_args.command]()
else:
    error("invalid command: '{0}' (choose from {1})".format(go_args.command, sorted(commands.keys())))
