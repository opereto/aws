import boto
import boto.cloudformation
import time
import sys
from opereto.helpers.services import ServiceTemplate
from opereto.utils.validations import JsonSchemeValidator
from opereto.exceptions import *

class ServiceRunner(ServiceTemplate):

    def __init__(self, **kwargs):
        ServiceTemplate.__init__(self, **kwargs)

    def setup(self):
        raise_if_not_ubuntu()


    def validate_input(self):
        input_scheme = {
            "type": "object",
            "properties" : {
                 "cf_stack_name": {
                     "type" : "string",
                     "minLength": 1
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
                 "required": ['cf_stack_name', 'aws_access_key','aws_secret_key', 'aws_region'],
                 "additionalProperties": True
            }
        }
        validator = JsonSchemeValidator(self.input, input_scheme)
        validator.validate()

        self.cf_stack_name = self.input['cf_stack_name']
        self.aws_access_key = self.input['aws_access_key']
        self.aws_secret_key = self.input['aws_secret_key']
        self.aws_region = self.input['aws_region']

        self._print_step_title('Connecting to AWS..')
        self.cf_conn = boto.cloudformation.connect_to_region(self.input['aws_region'], aws_access_key_id=self.input['aws_access_key'],
                                                        aws_secret_access_key=self.input['aws_secret_key'])
        print 'Connected.'

    def process(self):


        try:
            self._print_step_title('Deleting the topology stack (may take few minutes)...')
            print self.cf_conn.delete_stack(self.input['cf_stack_name'])
        except Exception, e:
            print >> sys.stderr, 'Topology deletion failed : %s.'%str(e)
            print >> sys.stderr, 'Please retry again later or delete the stack directly from AWS cloud formation console.'
            return self.client.FAILURE

        self._print_step_title('Verifying that the stack is deleted..')
        print 'Verifying that the stack is deleted..'
        while True:
            try:
                print self.cf_conn.describe_stacks(self.input['cf_stack_name'])[0].stack_status
                time.sleep(30)
            except Exception, e:
                if '%s does not exist'%self.input['cf_stack_name'] in str(e):
                    break
                else:
                    print str(e)
                    return self.client.FAILURE
        print 'Cloud formation stack has been deleted successfully.'
        return self.client.SUCCESS

    def teardown(self):
        pass



if __name__ == "__main__":
    exit(ServiceRunner().run())

