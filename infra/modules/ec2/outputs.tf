output "instance_id" {
  value = aws_instance.app.id
}

output "public_ip" {
  value = aws_instance.app.public_ip
}

output "role_arn" {
  value = aws_iam_role.instance.arn
}

output "role_name" {
  value = aws_iam_role.instance.name
}
