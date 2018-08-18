import boto3
import json
import os,sys,time
from opereto.helpers.services import ServiceTemplate
from opereto.utils.validations import JsonSchemeValidator, validate_dict
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
                 "bucket_name": {
                     "type" : "string",
                     "minLength": 1
                 },
                 "source_path": {
                     "type" : "string",
                     "minLength": 1
                 },
                 "target_path": {
                     "type" : "string",
                     "minLength": 1
                 },
                 "presigned_url_expiry": {
                     "type": "integer"
                 },
                 "create_bucket": {
                     "type" : "boolean"
                 },
                 "make_public": {
                     "type" : "boolean"
                 },
                 "content_type": {
                    "type": "string"
                 },
                 "aws_access_key": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "aws_secret_key": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "required": ['bucket_name', 'source_path', 'target_path', 'aws_access_key','aws_secret_key', 'content_type'],
                 "additionalProperties": True
            }
        }
        validator = JsonSchemeValidator(self.input, input_scheme)
        validator.validate()

        self.source_path = self.input['source_path']
        self.target_path = self.input['target_path'].lstrip('/')

        self.session = boto3.session.Session(
            aws_access_key_id=self.input['aws_access_key'],
            aws_secret_access_key=self.input['aws_secret_key']
        )
        self.s3_client = self.session.client('s3')
        self.s3_res = self.session.resource('s3')


    def process(self):

        self.acl = 'private'
        if self.input['make_public']:
            self.acl = 'public-read'
        if self.input['create_bucket']:
            self._print_step_title('Creating bucket {} if does not exist..'.format(self.input['bucket_name']))
            response = self.s3_client.create_bucket(
                ACL=self.acl,
                Bucket=self.input['bucket_name']
            )
            if validate_dict(response):
                print json.dumps(response, indent=4)

        time.sleep(1)  ## for logs to appear in right order
        self._print_step_title('Copying local data to s3..')

        if not os.path.exists(self.input['source_path']):
            raise OperetoRuntimeError('Source path does not exist')

        if os.path.isdir(self.input['source_path']):
            print 'Saving the content of directory {} to {} in bucket {}..'.format(self.source_path, self.target_path, self.input['bucket_name'])

            main_root_dir=os.path.basename(os.path.normpath(self.source_path))
            for root, dirs, files in os.walk(self.source_path):
                for name in files:
                    path = root[root.find(main_root_dir):].split(os.path.sep)
                    path.append(name)
                    target_id = '/'.join(path)
                    if self.target_path:
                        target_id = '%s/%s' % (self.target_path, target_id)
                    self.s3_res.meta.client.upload_file(os.path.join(root, name), self.input['bucket_name'], target_id, ExtraArgs={'ACL':self.acl, 'ContentType': self.input['content_type']})
        else:
            print 'Saving local file {} to {} in bucket {}..'.format(self.source_path, self.target_path, self.input['bucket_name'])
            self.s3_res.meta.client.upload_file(self.source_path, self.input['bucket_name'], self.target_path, ExtraArgs={'ACL':self.acl, 'ContentType': self.input['content_type']})

        print 'Operation completed successfuly.'

        if self.input['presigned_url_expiry']:
            print 'Generating pre-signed url expired in {} seconds..'.format(self.input['presigned_url_expiry'])
            presigned_url = self.s3_client.generate_presigned_url('get_object', Params={'Bucket': self.input['bucket_name'], 'Key': self.target_path}, ExpiresIn=self.input['presigned_url_expiry'])
            print '[OPERETO_HTML]<a target="_blank" href="' + presigned_url + '">'+ presigned_url +'</a>'
            print '\n\n'
            self.client.modify_process_property('storage_url', presigned_url)

        return self.client.SUCCESS

    def teardown(self):
        pass



if __name__ == "__main__":
    exit(ServiceRunner().run())

