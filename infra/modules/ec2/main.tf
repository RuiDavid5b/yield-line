data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023_arm" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-kernel-default-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }
}

resource "aws_security_group" "app" {
  name   = "yieldline-${var.environment}-app"
  vpc_id = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.app.id

  description = "SSH from own IP"

  cidr_ipv4   = var.ssh_ingress_cidr
  from_port   = 22
  to_port     = 22
  ip_protocol = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.app.id

  description = "HTTPS for FastAPI backend"

  cidr_ipv4   = "0.0.0.0/0"
  from_port   = 443
  to_port     = 443
  ip_protocol = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "all_ipv4" {
  security_group_id = aws_security_group.app.id

  description = "Allow outbound IPv4"

  cidr_ipv4   = "0.0.0.0/0"
  ip_protocol = "-1"
}

resource "aws_iam_role" "instance" {
  name = "yieldline-${var.environment}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "yieldline-${var.environment}-ec2-profile"
  role = aws_iam_role.instance.name
}

# ECR pull permissions - the instance needs this to `docker pull` the
# app image on deploy.
resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# SSM read permissions - for config.py's _settings_from_ssm() to fetch
# parameters at startup, plus SSM Session Manager for shell access
# without needing an open SSH port long-term (kept here alongside SSH
# ingress for now rather than replacing it - see note below).
resource "aws_iam_role_policy" "ssm_read" {
  name = "yieldline-${var.environment}-ssm-read"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:GetParameters"]
      Resource = "arn:aws:ssm:*:*:parameter/stock-news/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_managed_instance_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023_arm.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  tags = {
    Name = "yieldline-${var.environment}-app"
  }

  # Data volume is attached separately (aws_volume_attachment below),
  # not baked into root_block_device - keeps it independently
  # destroyable/persistent from the instance itself, per the
  # DeleteOnTermination concern flagged earlier.
  lifecycle {
    ignore_changes = [ami] # don't force replacement on every new AMI release - deploys happen via CI/CD image updates, not instance replacement
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
}

resource "aws_ebs_volume" "data" {
  availability_zone = aws_instance.app.availability_zone
  size              = var.data_volume_size_gb
  type              = "gp3"

  tags = {
    Name = "yieldline-${var.environment}-data"
  }

  lifecycle {
    prevent_destroy = true # the one thing that must never happen by accident - see EBS persistence discussion
  }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.app.id

  # Explicit: this attachment's underlying EBS volume must survive even
  # if the instance is terminated and replaced.
  stop_instance_before_detaching = true
}
