## Opereto AWS services

This package is a wrapper to several operations (as listed bellow) that are commonly used by opereto users maintaining a continuous testing ecosystem in AWS cloud environment. AWS provides a comprehensive set of API calls allowing to manage every resource and perform any operation available. In case you need additional devops operations, we recommend wrapping one of the many third-party libraries or command line toos available in the market and build your own opereto services based on those tools.
The package includes two services:

| Service                               | Description                                                                                                                   |
| --------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------:| 
| services/aws_create_cf_stack          | Creates cloud formation stack based on template provided including opereto agents installed on remote instances as needed     | 
| services/aws_create_cf_stack          | Removes any pre-defined cloud formation stack provided the stack name                                                         | 
| services/aws_get_from_s3              | Get files or directories from S3 storage and save in local path on the agent host                                             | 
| services/aws_save_to_s3               | Upload and save local files or directories to remote s3 storage                                                               | 


### Prerequisits/dependencies
* Services are mapped to run on a standard opereto worker agent
* opereto_core_services
        
        
### Service packages documentation
* [Learn more about automation packages and how to use them](http://help.opereto.com/support/solutions/articles/9000152583-an-overview-of-service-packages)
* [Learn more how to extend this package or build custom packages](http://help.opereto.com/support/solutions/articles/9000152584-build-and-maintain-custom-packages)

