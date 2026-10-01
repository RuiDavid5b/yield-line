#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

AWS_REGION="${AWS_REGION:-eu-west-2}"
SECRET_ID="yieldline/staging/app-secrets"
SSM_PREFIX="/stock-news/staging"
ENV_FILE="/run/yieldline/app.env"

mkdir -p /run/yieldline

SECRET_JSON="$(
    aws secretsmanager get-secret-value \
        --region "$AWS_REGION" \
        --secret-id "$SECRET_ID" \
        --query 'SecretString' \
        --output text
)"

if ! jq -e 'type == "object"' >/dev/null <<<"$SECRET_JSON"; then
    echo "Secrets Manager returned invalid secret JSON." >&2
    exit 1
fi

get_secret() {
    local key="$1"
    local value

    value="$(jq -r --arg key "$key" '.[$key] // empty' <<<"$SECRET_JSON")"

    if [[ -z "$value" ]]; then
        echo "Missing required secret: $key" >&2
        exit 1
    fi

    printf '%s' "$value"
}

get_parameter() {
    local name="$1"
    local value

    value="$(
        aws ssm get-parameter \
            --region "$AWS_REGION" \
            --name "$name" \
            --query 'Parameter.Value' \
            --output text
    )"

    if [[ -z "$value" || "$value" == "None" ]]; then
        echo "Missing required SSM parameter: $name" >&2
        exit 1
    fi

    printf '%s' "$value"
}

DATABASE_URL="$(get_secret DATABASE_URL)"
REDIS_URL="$(get_secret REDIS_URL)"
CURRENTS_API_KEY="$(get_secret CURRENTS_API_KEY)"
GOOGLE_API_KEY="$(get_secret GOOGLE_API_KEY)"

COGNITO_CLIENT_ID="$(get_parameter "$SSM_PREFIX/cognito_client_id")"
COGNITO_USER_POOL_ID="$(get_parameter "$SSM_PREFIX/cognito_user_pool_id")"
BYOK_KMS_KEY_ALIAS="$(get_parameter "$SSM_PREFIX/byok_kms_key_alias")"
EDGAR_USER_AGENT="$(get_parameter "$SSM_PREFIX/edgar_user_agent")"

umask 077

tmp="$(mktemp /run/yieldline/app.env.XXXXXX)"
trap 'rm -f "$tmp"' EXIT

cat > "$tmp" <<EOF
DATABASE_URL=$DATABASE_URL
REDIS_URL=$REDIS_URL
CURRENTS_API_KEY=$CURRENTS_API_KEY
GOOGLE_API_KEY=$GOOGLE_API_KEY
AWS_REGION=$AWS_REGION
COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID
COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID
BYOK_KMS_KEY_ALIAS=$BYOK_KMS_KEY_ALIAS
EDGAR_USER_AGENT=$EDGAR_USER_AGENT
EOF

chown root:root "$tmp"
chmod 600 "$tmp"
mv "$tmp" "$ENV_FILE"

trap - EXIT

echo "Runtime environment written successfully."
