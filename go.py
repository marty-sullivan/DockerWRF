#!/usr/bin/env python

# Standard Imports
from __future__ import print_function
from os import chmod, path, remove
from shutil import rmtree
from sys import exit, stderr
from threading import Thread
from time import sleep
from urllib2 import urlopen
import yaml
import json

# Constants

TAG_PREFIX = 'wrf-ecs-{0}-'
IAM_PATH = '/{0}/'
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
    r['iam_path'] = IAM_PATH.format(r['prefix'][:-1])

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
    r['aws']['roles'] = list(r['iam'].roles.filter(PathPrefix=r['iam_path']))
    r['aws']['instance_profiles'] = list(r['iam'].instance_profiles.filter(PathPrefix=r['iam_path']))

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

    # Enumerate Resource ID / Names
    r['resource_ids'] = []
    for resource in r['aws']:
        if resource == 'subnets':
            continue
        elif resource == 'clusters':
            for cluster in r['aws'][resource]:
                r['resource_ids'].append(cluster['clusterName'])
        elif resource == 'head_nodes' or resource == 'worker_nodes':
            for instance in r['aws'][resource]:
                r['resource_ids'].append(instance.id)
        elif resource == 'security_groups':
            for security_group in r['aws'][resource]:
                r['resource_ids'].append(security_group.group_name)
        else:
            for res in r['aws'][resource]:
                r['resource_ids'].append(res.name)

    return r

# Functions
def create_aws():
    r = get_aws_resources()

    if r['resource_count'] > 0:
        error('There are existing resources for the label: {0}. Run ./go.py destroy_aws to remove them.')
        exit(1)

    # IAM Role
    r['aws']['roles'] = []
    #r['aws']['roles'][0] = r['iam'].create_role(Path='/' + r['prefix'] + 'roles', RoleName=r['prefix'] + 'role', AssumeRolePolicyDocument=ECS_ASSUME_ROLE_POLICY_DOC)
    r['aws']['roles'].append(r['iam'].create_role(Path=r['iam_path'], RoleName=r['prefix'] + 'role', AssumeRolePolicyDocument=ECS_ASSUME_ROLE_POLICY_DOC))
    r['aws']['roles'][0].attach_policy(PolicyArn=ECS_ROLE_POLICY_ARN)
        
    # IAM Instance Profile
    r['aws']['instance_profiles'] = []
    r['aws']['instance_profiles'].append(r['iam'].create_instance_profile(Path=r['iam_path'], InstanceProfileName=r['prefix'] + 'profile'))
    r['aws']['instance_profiles'][0].add_role(RoleName=r['aws']['roles'][0].role_name)

    # Security Group
    r['aws']['security_groups'] = []
    r['aws']['security_groups'].append(r['aws']['subnets'][0].vpc.create_security_group(GroupName=r['prefix'] + 'sg', Description=r['prefix'] + 'sg'))
    r['aws']['security_groups'][0].authorize_ingress(IpPermissions=[
        { 'IpProtocol': '-1', 'FromPort': 0, 'ToPort': 65535, 'UserIdGroupPairs': [{ 'GroupId': r['aws']['security_groups'][0].group_id }] },
        { 'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{ 'CidrIp': r['config']['ssh-cidr'] }] }
    ])

    # Placement Group
    r['aws']['placement_groups'] = []
    r['aws']['placement_groups'].append(r['ec2'].create_placement_group(GroupName=r['prefix'] + 'placement', Strategy='cluster'))

    # Key Pair
    r['aws']['key_pairs'] = []
    r['aws']['key_pairs'].append(r['ec2'].create_key_pair(KeyName=r['prefix'] + 'keypair'))
    with open('./keys/' + r['aws']['key_pairs'][0].key_name + '.pem', 'w') as pem:
        pem.write(r['aws']['key_pairs'][0].key_material)
        chmod('./keys/' + r['aws']['key_pairs'][0].key_name + '.pem', 0600)

    # ECS Cluster
    r['aws']['clusters'] = []
    r['aws']['clusters'].append(r['ecs'].create_cluster(clusterName=r['prefix'] + 'cluster'))

    sleep(10)

    # Head Node Block Devices
    head_block_devices = [
    {
        'DeviceName': '/dev/sdb',
        'Ebs': {
            'SnapshotId': r['config']['ebs-snapshot'],
            'VolumeSize': r['config']['ebs-size-gb'],
            'DeleteOnTermination': True,
            'VolumeType': 'gp2'
        }
    }]

    if r['config']['ebs-iops'] > 0:
        head_block_devices[0]['Ebs']['VolumeType'] = 'io1'
        head_block_devices[0]['Ebs']['Iops'] = r['config']['ebs-iops']

    # Head Node User Data
    with open('./user-data/head', 'r') as ud:
        head_ud = ud.read()

    # Head Node Instance
    r['aws']['head_nodes'] = r['ec2'].create_instances(ImageId=r['config']['base-ami'], \
                    MinCount=1, \
                    MaxCount=1, \
                    KeyName=r['aws']['key_pairs'][0].key_name, \
                    UserData=head_ud, \
                    InstanceType=r['config']['instance-type'], \
                    Placement={ 'GroupName': r['aws']['placement_groups'][0].group_name, 'Tenancy': r['config']['tenancy'] }, \
                    BlockDeviceMappings=head_block_devices, \
                    Monitoring={ 'Enabled': r['config']['monitoring'] }, \
                    InstanceInitiatedShutdownBehavior='terminate', \
                    NetworkInterfaces=[{ 
                        'DeviceIndex': 0, 
                        'SubnetId': r['aws']['subnets'][0].subnet_id, 
                        'Groups': [r['aws']['security_groups'][0].group_id],
                        'AssociatePublicIpAddress': True
                    }], \
                    IamInstanceProfile={ 'Arn': r['aws']['instance_profiles'][0].arn })

    # Head Node Network Interface
    head_network = r['aws']['head_nodes'][0].network_interfaces[0]

    # Worker Node User Data
    with open('./user-data/worker', 'r') as ud:
        worker_ud = ud.read()
        worker_ud = worker_ud.replace('%NFS_HOST%', head_network.private_ip_address)

    r['aws']['worker_nodes'] = r['ec2'].create_instances(ImageId=r['config']['base-ami'], \
                       MinCount=r['global']['nodes'], \
                       MaxCount=r['global']['nodes'], \
                       KeyName=r['aws']['key_pairs'][0].key_name, \
                       UserData=worker_ud, \
                       InstanceType=r['config']['instance-type'], \
                       Placement={ 'GroupName': r['aws']['placement_groups'][0].group_name, 'Tenancy': r['config']['tenancy'] }, \
                       Monitoring={ 'Enabled': r['config']['monitoring'] }, \
                       InstanceInitiatedShutdownBehavior='terminate', \
                       NetworkInterfaces=[{ 
                           'DeviceIndex': 0, 
                           'SubnetId': r['aws']['subnets'][0].subnet_id, 
                           'Groups': [r['aws']['security_groups'][0].group_id], 
                           'AssociatePublicIpAddress': True 
                       }], \
                       IamInstanceProfile={ 'Arn': r['aws']['instance_profiles'][0].arn })

    print('All resources are created. Waiting for nodes to be ready.')
    for instance in r['aws']['head_nodes']:
        instance.create_tags(Tags=[{ 'Key': 'Name', 'Value': r['prefix'] + 'head' }])
        instance.wait_until_running()
    
    for instance in r['aws']['worker_nodes']:
        instance.create_tags(Tags=[{ 'Key': 'Name', 'Value': r['prefix'] + 'worker' }])
        instance.wait_until_running()

    #TODO: Add to ECS Cluster

    print('Cluster Ready')
        

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

    # Confirm Destruction
    print('\n*** The following resources will be DESTROYED. Type DESTROY to continue or anything else to cancel. ***\n')
    for i in r['resource_ids']:
        print(i)
    print('')
    response = raw_input('--> ')
    if response != 'DESTROY':
        exit(0)

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

    # Role & Instance Profile
    for role in r['aws']['roles']:
        for instance_profile in role.instance_profiles.all():
            instance_profile.remove_role(RoleName=role.name)
            instance_profile.delete()
        for policy in role.attached_policies.all():
            role.detach_policy(PolicyArn=policy.arn)
        role.delete()
        
    # Security Group
    for sg in r['aws']['security_groups']:
        sg.delete()

    # Placement Group
    for pg in r['aws']['placement_groups']:
        pg.delete()

    # Key Pair
    for keypair in r['aws']['key_pairs']:
        remove('./keys/' + keypair.key_name + '.pem')
        keypair.delete()

commands = { 'create_aws': create_aws, 'destroy_aws': destroy_aws }

# Entry

if go_args.command in commands:
    commands[go_args.command]()
else:
    error("invalid command: '{0}' (choose from {1})".format(go_args.command, sorted(commands.keys())))
