output "repository_urls" {
  description = "Map of repository short name (app/api) to its full registry URL"
  value       = { for name, repo in aws_ecr_repository.this : name => repo.repository_url }
}
