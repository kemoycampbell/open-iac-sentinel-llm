variable "region" {
  default     = "us-east-1"
  type        = string
  description = "The AWS region to deploy resources in."
}

variable "instance_type" {
  default     = "t2.micro"
  type        = string
  description = "The type of EC2 instance to use."
}

variable "use_localstack" {
  default     = true
  type        = bool
  description = "Whether to use LocalStack for testing."
}

variable "tag" {
  default     = "OpenIACSentinel"
  type        = string
  description = "Tag to identify resources created by this configuration."
}