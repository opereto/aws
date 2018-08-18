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
                 "aws_access_key": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "aws_secret_key": {
                    "type" : "string",
                     "minLength": 1
                 },
                 "required": ['bucket_name', 'source_path', 'target_path', 'aws_access_key','aws_secret_key'],
                 "additionalProperties": True
            }
        }
        validator = JsonSchemeValidator(self.input, input_scheme)
        validator.validate()

        self.source_path = self.input['source_path']
        self.target_path = self.input['target_path']

        self.session = boto3.session.Session(
            aws_access_key_id=self.input['aws_access_key'],
            aws_secret_access_key=self.input['aws_secret_key']
        )
        self.s3_client = self.session.client('s3')
        self.s3_res = self.session.resource('s3')

    def process(self):

        def download_dir(client, resource, dist, local, bucket):
            paginator = client.get_paginator('list_objects')
            for result in paginator.paginate(Bucket=bucket, Delimiter='/', Prefix=dist):
                if result.get('CommonPrefixes') is not None:
                    for subdir in result.get('CommonPrefixes'):
                        download_dir(client, resource, subdir.get('Prefix'), local, bucket)
                if result.get('Contents') is not None:
                    for file in result.get('Contents'):
                        if not os.path.exists(os.path.dirname(local + os.sep + file.get('Key'))):
                             os.makedirs(os.path.dirname(local + os.sep + file.get('Key')))
                        resource.meta.client.download_file(bucket, file.get('Key'), local + os.sep + file.get('Key'))


        if self.input['is_directory']:
            print 'Fetching the content of {} recursively from bucket {} to directory {}..'.format(self.source_path, self.input['bucket_name'], self.target_path)
            download_dir(self.s3_client, self.s3_res, self.source_path, self.target_path, self.input['bucket_name'])
        else:
            print 'Fetching the content of {} from bucket {} to local file {}..'.format(self.source_path, self.input['bucket_name'], self.target_path)
            self.s3_res.meta.client.download_file(self.input['bucket_name'], self.source_path, self.target_path)

        print 'Operation completed successfuly.'
        return self.client.SUCCESS

    def teardown(self):
        pass



if __name__ == "__main__":
    exit(ServiceRunner().run())

