import boto
import boto.cloudformation
import boto.ec2
import json
import time
import sys
import uuid
import socket
from opereto.helpers.services import ServiceTemplate
from opereto.utils.validations import JsonSchemeValidator, default_variable_name_scheme, default_entity_name_scheme, default_entity_description_scheme
from opereto.utils.misc import retry
from opereto.exceptions import *

class ServiceRunner(ServiceTemplate):

    def __init__(self, **kwargs):
        ServiceTemplate.__init__(self, **kwargs)

    def setup(self):
        raise_if_not_ubuntu()
        self.agents = {}

    def validate_input(self):
        input_scheme = {
            "type": "object",
            "properties" : {
                 "cf_stack_name": {
                     "type" : "string",
                     "minLength": 1
                 },
                 "cf_template": {
                    "type" : ["object", "null"]
                },
                "cf_template_url": {
                    "type": ["string", "null"]
                },
                 "opereto_core_tools": {
                    "type" : "boolean"
                 },
                 "opereto_container_tools": {
                    "type" : "boolean"
                 },
                 "agent_package_url": {
                    "type": "object",
                    "properties": {
                        "windows": {
                            "type": "string",
                            "minLength": 1
                        },
                        "linux": {
                            "type": "string",
                            "minLength": 1
                        }
                    },
                     "required": ['windows', 'linux'],
                     "additionalProperties": True
                },
                "disable_rollback": {
                    "type": "boolean"
                },
                 "cf_capabilities": {
                    "type" : ["string", "null"]
                 },
                 "cf_parameters": {
                    "type" : ["object", "null"]
                 },
                 "cf_tags": {
                    "type" : ["object", "null"]
                 },
                "cf_globals": {
                    "type": ["object", "null"]
                 },
                 "aws_access_key": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "aws_secret_key": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "aws_region": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "required": ['aws_access_key','aws_secret_key', 'aws_region'],
                 "additionalProperties": True
            }
        }
        validator = JsonSchemeValidator(self.input, input_scheme)
        validator.validate()


        self.cf_template = self.input['cf_template']
        self.cf_template_url = self.input['cf_template_url']
        if not self.cf_template and not self.cf_template_url:
            raise Exception, 'Cloud formation template json (or an s3 url of a template) must be provided.'

        self.install_core_tools = self.input['install_core_tools']
        self.install_container_tools = self.input['install_container_tools']
        self.agent_valid_os = ['linux', 'windows']
        self.cf_capabilities = self.input['cf_capabilities'].split(',')
        self.cf_globals = self.input['cf_globals']

        if self.install_container_tools and not self.install_core_tools:
            raise Exception, 'Opereto container tools is dependant on opereto core tools. Please check the "install_core_tools" checkbox too.'

        source_user = self.client.input['opereto_originator_username']
        self.users = [source_user]
        self.owners = [source_user]

        def windows_user_data(agent_name):
            data = [
                "<powershell>",
                "Add-Type -AssemblyName System.IO.Compression.FileSystem",
                "function Unzip",
                "{",
                "    param([string]$zipfile, [string]$outpath)",
                "    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipfile, $outpath)",
                "}",
                "$MyDir = \"c:\"",
                "$filename = Join-Path -Path $MyDir -ChildPath \"opereto-agent-latest.zip\"",
                "$WebClient = New-Object System.Net.WebClient",
                "$WebClient.DownloadFile(\"%s\", \"$filename\")" %(self.input['agent_package_url']['windows']),
                "Unzip \"$MyDir\opereto-agent-latest.zip\" \"$MyDir\opereto\"",
                "cd \"$MyDir\opereto\opereto-agent-latest\"",
                "./opereto-install.bat %s %s %s javaw" %(self.input['opereto_host'], self.input['opereto_token'], agent_name),
                "./opereto-start.bat",
                "Remove-Item $filename",
                "</powershell>",
                "<persist>true</persist>"
            ]
            return data


        def linux_user_data(agent_name):

            data = [
                "#!/bin/bash -x",
                "exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1",
                "sed --in-place /requiretty/d /etc/sudoers",
                "cd /tmp",
                "curl -O %s" %(self.input['agent_package_url']['linux']),
                "tar -zxvf opereto-agent-latest.tar.gz",
                "cd opereto-agent-latest",
                "sudo chmod 777 -R *",
                "./install.sh -h %s -t %s -n %s"%(self.input['opereto_host'], self.input['opereto_token'], agent_name)
            ]
            return data

        if "Resources" in self.cf_template:
            for resource_name, resource_data in self.cf_template['Resources'].items():
                if resource_data["Type"]=="AWS::EC2::Instance":

                    agent_os=None
                    agent_name=None
                    agent_display_name=None
                    agent_description=None
                    agent_id_found=False
                    for tag in resource_data["Properties"]["Tags"]:
                        if tag['Key']=='OperetoAgentOs':
                            agent_os=tag['Value']
                        elif tag['Key']=='OperetoAgentId':
                            agent_id_found=True
                            agent_name=tag['Value']
                        elif tag['Key']=='OperetoAgentName':
                            agent_display_name=tag['Value']
                        elif tag['Key']=='OperetoAgentDesc':
                            agent_description=tag['Value']

                    if agent_os:
                        if agent_os not in self.agent_valid_os:
                            raise OperetoRuntimeError('OperetoAgentOs must be one of the following: {}'.format(str(self.agent_valid_os)))
                        if not agent_name:
                            agent_name = 'agent'+str(uuid.uuid4())[:10]
                        else:
                            try:
                                JsonSchemeValidator(agent_name, default_variable_name_scheme).validate()
                            except Exception,e:
                                raise OperetoRuntimeError('Invalid agent identifier: {}'.format(str(e)))
                        if agent_display_name:
                            try:
                                JsonSchemeValidator(agent_display_name, default_entity_name_scheme).validate()
                            except Exception,e:
                                raise OperetoRuntimeError('Invalid agent name: {}'.format(str(e)))
                        if agent_description:
                            try:
                                JsonSchemeValidator(agent_description, default_entity_description_scheme).validate()
                            except Exception,e:
                                raise OperetoRuntimeError('Invalid agent description: {}'.format(str(e)))

                        if agent_os=='windows':
                            agent_data = windows_user_data(agent_name)
                        else:
                            agent_data = linux_user_data(agent_name)

                        ## currently override user data, add fix to handle addition to existing user data
                        ##
                        ##
                        self.cf_template["Resources"][resource_name]["Properties"]["UserData" ] = {
                            "Fn::Base64": {
                                "Fn::Join": ["\n", agent_data]
                            }
                        }
                        if not agent_id_found:
                            self.cf_template["Resources"][resource_name]["Properties"]["Tags" ].append({
                                "Key": "OperetoAgentId",
                                "Value": agent_name
                            })

                        self.agents[agent_name]={
                            'cf_stack_name': self.input['cf_stack_name'],
                            'agent_display_name': agent_display_name,
                            'agent_description': agent_description
                        }

        self._print_step_title('Connecting to AWS..')
        self.cf_conn = boto.cloudformation.connect_to_region(self.input['aws_region'], aws_access_key_id=self.input['aws_access_key'],
                                                        aws_secret_access_key=self.input['aws_secret_key'])
        self.ec2_conn = boto.ec2.connect_to_region(self.input['aws_region'], aws_access_key_id=self.input['aws_access_key'], aws_secret_access_key=self.input['aws_secret_key'])
        print 'Connected.'




    def process(self):

        self.stack_full_id=None
        self.stack_output = {}

        @retry(10,60,1)
        def verify_that_all_agents_connected():
            for agent_name, attr in self.agents.items():
                print 'Checking if agent %s is up and running'%agent_name
                try:
                    self.client.get_agent_properties(agent_name)
                except:
                    print 'Agent %s is not up yet. Recheck in one minute..'%agent_name
                    raise
                print 'Agent %s is up and running.'%agent_name
            pass

        try:
            self._print_step_title('Creating the cloud formation stack..')
            additional_params = {}
            if self.cf_capabilities:
                print 'Capabilities are: {}'.format(self.input['cf_capabilities'])
                additional_params['capabilities']=self.cf_capabilities

            if self.input['cf_parameters']:
                cf_params = self.input['cf_parameters']
                if self.cf_globals:
                    for key,val in cf_params.items():
                        if val.startswith('cf_globals.'):
                            new_val = self.cf_globals.get(val[len('cf_globals.'):])
                            cf_params[key]=new_val
                additional_params['parameters']=cf_params.items()

            if self.input['cf_tags']:
                additional_params['tags']=self.input['cf_tags']

            if self.input.get('disable_rollback'):
                additional_params['disable_rollback'] = True

            if self.cf_template_url:
                additional_params['template_url'] = self.cf_template_url

            if self.cf_template:
                additional_params['template_body'] = json.dumps(self.cf_template)

            self.stack_full_id = self.cf_conn.create_stack(self.input['cf_stack_name'], **additional_params)


            if len(self.cf_conn.describe_stacks(self.stack_full_id))==1:
                print 'Stack created (%s)'%self.stack_full_id
                self._print_step_title('Waiting for cloud formation initiation to complete (may take few minutes)..')
                while True:
                    if self.cf_conn.describe_stacks(self.stack_full_id)[0].stack_status == 'CREATE_COMPLETE':
                        break
                    if self.cf_conn.describe_stacks(self.stack_full_id)[0].stack_status in ['CREATE_FAILED', 'ROLLBACK_COMPLETE']:
                        cf_error = {}
                        cf_error_msg=[]
                        for e in self.cf_conn.describe_stack_events(self.stack_full_id):
                            cf_error[e.logical_resource_id] = {
                                'status': e.resource_status,
                                'reason': e.resource_status_reason
                            }
                            error_msg = '%s [%s]: %s'%(e.logical_resource_id, e.resource_status, e.resource_status_reason)
                            print(error_msg)
                            cf_error_msg.append(error_msg)
                        self.stack_output['cf_error']='\n'.join(cf_error_msg)
                        return self.client.FAILURE
                    time.sleep(20)

                print "Cloud formation stack has been created successfully.."
                outputs = self.cf_conn.describe_stacks(self.stack_full_id)[0].outputs
                for output_obj in outputs:
                    self.stack_output[output_obj.key]=output_obj.value

                self._print_step_title('Waiting that all instances will be up..')
                wait=False
                while True:
                    resources = self.cf_conn.describe_stack_resources(self.stack_full_id)
                    for resource in resources:
                        if resource.resource_type=='AWS::EC2::Instance':
                            reservations = self.ec2_conn.get_all_instances([resource.physical_resource_id])
                            instance = reservations[0].instances[0]
                            agent_name = instance.tags.get('OperetoAgentId')
                            if agent_name:
                                for k,v in instance.__dict__.items():
                                    self.agents[agent_name]['aws_'+k]=str(v)
                                self.agents[agent_name]['aws_region']=self.input['aws_region']
                            if not str(instance._state).startswith('running'):
                                wait=True
                                break

                    if not wait:
                        break
                    time.sleep(20)

                print 'All instances are running.'


                self.client.modify_process_property('stack_id', self.stack_full_id)
                for agent_name, attr in self.agents.items():
                    self.agents[agent_name]['cf_stack_id']=self.stack_full_id

                self._print_step_title('Test SSH connectivity to all instances..')
                ## test connectivity
                for agent_name, attr in self.agents.items():
                    if attr.get('ip_address'):
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            print 'Testing ssh connectivity to %s'%agent_name
                            s.connect((attr['ip_address'], 22))
                            print "Port 22 reachable"
                            s.close()
                            time.sleep(2)
                        except socket.error as e:
                            print "Error on connect: %s" % e
                            s.close()


                ## check agents installation
                if self.agents:
                    self._print_step_title('Verify agents installation and configuration..')

                try:
                    verify_that_all_agents_connected()
                except:
                    raise OperetoRuntimeError('One or more agents failed to install. aborting..')

                ## modify agent properties
                for agent_name, attr in self.agents.items():
                    try:
                        self.client.modify_agent_properties(agent_name, attr)
                    except Exception,e:
                        print e

                    ## modify agent permissions
                    permissions = {
                        'owners': self.users,
                        'users': self.owners
                    }
                    description = attr.get('agent_description') or 'Created by cloud formation stack'
                    agent_display_name = attr.get('agent_display_name') or agent_name
                    self.client.modify_agent(agent_name, name=agent_display_name, description=description, permissions=permissions)

            else:
                raise OperetoRuntimeError('No cloud formation stack found.')


            if self.install_core_tools:
                install_list=[]
                for agent_name, attr in self.agents.items():
                    title = 'Installing opereto worker libraries on agent {}'.format(agent_name)
                    install_list.append(self.client.create_process(service='install_opereto_worker_libs', agent=agent_name, title=title))

                if not self.client.is_success(install_list):
                    raise OperetoRuntimeError('Failed to install opereto worker libraries on one or more agents')

                time.sleep(10)
                if self.install_container_tools:

                    install_list_2=[]
                    for agent_name, attr in self.agents.items():
                        title = 'Installing opereto container tools on agent {}'.format(agent_name)
                        install_list_2.append(self.client.create_process(service='install_docker_on_host', agent=agent_name, title=title))

                    if not self.client.is_success(install_list_2):
                        raise OperetoRuntimeError('Failed to install opereto container tools on one or more agents')

            print 'Cloud formation stack created successfully.'
            return self.client.SUCCESS

        except Exception, e:

            ### TBD: add to service template
            import re
            err_msg = re.sub("(.{9900})", "\\1\n", str(e), 0, re.DOTALL)
            print >> sys.stderr, 'Cloud formation stack initiation failed : %s.'%err_msg
            self.stack_output['cf_error']=err_msg
            if self.stack_full_id and not self.input.get('disable_rollback'):
                print 'Rollback the stack..'
                print self.cf_conn.delete_stack(self.stack_full_id)
            return self.client.FAILURE

        finally:
            self.client.modify_process_property('stack_output', self.stack_output)


    def teardown(self):
        pass



if __name__ == "__main__":
    exit(ServiceRunner().run())
