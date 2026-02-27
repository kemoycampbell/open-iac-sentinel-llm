# Infrastructure Drift Categories
Infrastructure drifts can be categorized into different types based on the
nature or method of the changes.

We can categorize infrastructure drifts into the following types:

## Property Modification drifts
This involves changing the resource values so that the state
and the cloud diverge.

### Example:
#### Secuirty Group Rule Changed

- **Security Group from_port**: `22 → 2222`
- **EC2 Instance Type**: `t2.micro → t2.large`

  
## Configuration Toggles & Flags drifts
The setting doesnt involves add/remove resources but a change in the resource flags or toggles.
### Example:
- **S3 Bucket Versioning**: `true → false`
- **S3 Public Access Block**: `true → false`


## Resource Addition/Removal drifts
This involves in adding or removing from existing infrastructure which is not reflected in the terraform configuration.
This doesnt consider a brand new resource added to the infrastructure but rather resources that are already managed by the terraform
but has been removed or added in the cloud without reflecting in the terraform configuration.
### Example:
- **Subnets Count**: `2 → 3`
- **Security Group Rules Count**: `2 → 3`
- **Network Ports Count**: `2 → 3`
  
## Identity & Access Drifts (IAM Drift)
This involves changes in the IAM policies, roles, or permissions.

### Example:
- **IAM Role Permissions**: `read-only → read-write`
- **IAM Policy Changes**: `policy A → policy B`
- **IAM User Access Keys**: `active → inactive`
  
## Relationship & Attachment Drifts
This involves changes in the relationships or attachments between resources.

### Example:
- **EC2 Instance Security Group Attachment**: `attached to SG1 → attached to SG2`
- **Load Balancer Target Group Attachment**: `attached to Target Group A → attached to Target Group B`


## Defaults & Empherals drifts
This involves changes in the default values of the resources or ephemeral values that are not reflected in the terraform configuration.

AWS often updates the default values for the resources and this can cause drifts if the terraform configuration does not explicitly set these values.

### Example:
- **Default VPC CIDR Block**: `implicit/default → AWS-updated value`
- **Default Security Group Rules**: `no rules defined → AWS-added rules`


Notes: I think it is best to ignore drifts that are related to defaults and ephemeral values as these are often out of the control of the user, changes oftens. I consider these drifts as noise and not actionable drifts. However, it is still important to be aware of these drifts as they can cause unexpected behavior in the infrastructure.