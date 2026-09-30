resource "aws_s3_bucket" "frontend" {
  bucket = "yieldline-${var.environment}-frontend"
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  # Fully private - Caddy on the instance pulls via `aws s3 sync` using
  # the instance's own IAM role, never served directly from S3/public.
  # This is purely a CI-to-instance file transfer hop, not a CDN.
}
