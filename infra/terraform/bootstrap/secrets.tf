# Secret containers only: no aws_secretsmanager_secret_version, so values never reach state.
# Values are set out of band by ./put-secrets.sh.
resource "aws_secretsmanager_secret" "jev" {
  name        = "lb-demo/jev"
  description = "Jev API credential"
  lifecycle {
    prevent_destroy = true
  }
}

# Value is the RSA 2048 private key as a PEM string (identity/lambda_handler.py reads SecretString as PEM).
resource "aws_secretsmanager_secret" "idp_signing_key" {
  name        = "lb-demo/idp-signing-key"
  description = "Mock IdP RS256 signing key (PEM)"
  lifecycle {
    prevent_destroy = true
  }
}

output "jev_secret_arn" {
  value = aws_secretsmanager_secret.jev.arn
}

output "idp_signing_secret_arn" {
  value = aws_secretsmanager_secret.idp_signing_key.arn
}
