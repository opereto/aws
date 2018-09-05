This service creates cloud formation stack in AWS given account/region.

It gets a valid cloud formation template as an input and creates the cf stack. In addition, it allows automatically installing opereto agent and tools on specified instances as defined in the template.
Agent installation is performed by adding a short script to the user data field of the instance resource in the cf template. 

To require agent installation on a given instance, you have to add a tag to any relevant instance resource in your template as follows:

*"OperetoAgentOs"* tag with on of the following values: linux or windows. This directs the service code which agent installation script to use.   

In addition, you may add the following optional agent tags:

*"OperetoAgentId"* - pre-defined unique agent identifier. if not provided, opereto will automatically create a unique identifier (recommended)

*"OperetoAgentName"* - a display name to show in the UI

*"OperetoAgentDesc"* - a short custom description about this agent

For example: 

```
{
    "Resources": {
        "Node1": {
            "Type": "AWS::EC2::Instance",
            "Properties": {
                "ImageId": "ami-a4dc46db",
                "KeyName": "OperetoBox",
                "SecurityGroups": [
                    {
                        "Ref": "InstanceSecurityGroup"
                    }
                ],
                "InstanceType": "m4.large",
                "Tags": [
                    {
                        "Key": "OperetoAgentOs",
                        "Value": "linux"
                    }
                ]
            }
        }
...
...
``` 

#### Use cf_globals property 
This property is allows to specify opereto global property containing secret values (e.g. passwords, access credentials) to pass as parameters to cloud formation template
For example, you can pass some secret parameters to the cloud formation template making sure they are not exposed in opereto input property screens and in logs.

* Create a hidden global property in opereto (e.g. my_cf_secret_params)
* Specify your secret parameters as a key-value map
```
{
   "my_secret_key" : "my_secret_value"
}
```
* Pass the property name (e.g. my_cf_secret_params) as a value to the cf_globals input property
* In the cloud formation template, map a given parameter value to the relevant value in the map as follows:
```
SomeParam: globals.my_secret_key
```





#### Service success criteria
Success if stack created successfuly. Otherwise, Failure.

#### Assumptions/Limitations
* Requires that opereto worker lib is installed (see package opereto_core_services)
* If you choose to install opereto agent on a given instance, the agent installation script overrides any user data specified for that instance
* Automatically removes the created stack upon failure

#### Dependencies
No dependencies.