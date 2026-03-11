data "aws_ami" "ubuntu" {
  most_recent = true
  count       = var.use_localstack ? 0 : 1

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

locals {
  # Use a dummy AMI ID when using LocalStack, otherwise use the latest Ubuntu AMI
  ami_id = var.use_localstack ? "ami-12345678" : data.aws_ami.ubuntu[0].id
}

resource "aws_instance" "example" {
  ami           = local.ami_id
  instance_type = var.instance_type

  tags = {
    Name = var.tag
  }
}