#!/usr/bin/env bash
# Deploy ghcr.io/edjchapman/foreman:<version> to Railway (web -> worker -> beat).
#
# Railway does not watch GHCR: pushing a new tag deploys nothing, and
# `railway redeploy` re-runs the *previous* deployment with its original image
# reference. So CD is: pin each service's image to the exact semver tag
# (serviceInstanceUpdate), then create a fresh deployment
# (serviceInstanceDeployV2) via the public GraphQL API. Semver pinning keeps
# every Railway deployment reproducible and makes dashboard rollback
# meaningful (an old deployment re-runs the old version).
#
# ORDERING IS LOAD-BEARING: web deploys first and must reach SUCCESS before
# worker/beat are touched. Web's pre-deploy command runs `manage.py migrate`
# and its /readyz healthcheck gates the cutover — so new worker code never
# runs ahead of its migrations. A failed web deploy aborts the whole rollout
# (Railway keeps the previous deployment serving).
#
# ENV CONTRACT (all required):
#   RAILWAY_TOKEN              project token (env-scoped) — sent as
#                              Project-Access-Token. Set RAILWAY_TOKEN_KIND=account
#                              to send an account token as Authorization: Bearer.
#   RAILWAY_ENVIRONMENT_ID     the production environment id
#   RAILWAY_WEB_SERVICE_ID     service ids (dashboard URL or `railway status --json`)
#   RAILWAY_WORKER_SERVICE_ID
#   RAILWAY_BEAT_SERVICE_ID
#
# USAGE: railway-deploy.sh <version>        e.g. railway-deploy.sh 0.7.0
#
# NOTE: Railway returns HTTP 200 for GraphQL-level errors, so every response
# is checked for an `errors` key — curl -f alone is not enough.

set -euo pipefail

VERSION="${1:?usage: railway-deploy.sh <version>}"
IMAGE="ghcr.io/edjchapman/foreman:${VERSION}"
API="https://backboard.railway.com/graphql/v2"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-600}"
POLL_SECONDS=10

: "${RAILWAY_TOKEN:?RAILWAY_TOKEN is required}"
: "${RAILWAY_ENVIRONMENT_ID:?RAILWAY_ENVIRONMENT_ID is required}"
: "${RAILWAY_WEB_SERVICE_ID:?RAILWAY_WEB_SERVICE_ID is required}"
: "${RAILWAY_WORKER_SERVICE_ID:?RAILWAY_WORKER_SERVICE_ID is required}"
: "${RAILWAY_BEAT_SERVICE_ID:?RAILWAY_BEAT_SERVICE_ID is required}"

if [[ "${RAILWAY_TOKEN_KIND:-project}" == "account" ]]; then
  AUTH_HEADER="Authorization: Bearer ${RAILWAY_TOKEN}"
else
  AUTH_HEADER="Project-Access-Token: ${RAILWAY_TOKEN}"
fi

gql() { # gql <json-body> -> response body (fails on transport or GraphQL errors)
  local body response
  body="$1"
  response="$(curl -sSf "$API" -H "$AUTH_HEADER" -H 'Content-Type: application/json' -d "$body")"
  if jq -e '.errors' <<<"$response" >/dev/null 2>&1; then
    echo "GraphQL error: $(jq -c '.errors' <<<"$response")" >&2
    return 1
  fi
  printf '%s' "$response"
}

set_image() { # set_image <service-id>
  gql "$(jq -n --arg s "$1" --arg e "$RAILWAY_ENVIRONMENT_ID" --arg i "$IMAGE" '{
    query: "mutation($s:String!,$e:String!,$in:ServiceInstanceUpdateInput!){serviceInstanceUpdate(serviceId:$s,environmentId:$e,input:$in)}",
    variables: {s: $s, e: $e, in: {source: {image: $i}}}
  }')" >/dev/null
}

deploy() { # deploy <service-id>
  gql "$(jq -n --arg s "$1" --arg e "$RAILWAY_ENVIRONMENT_ID" '{
    query: "mutation($s:String!,$e:String!){serviceInstanceDeployV2(serviceId:$s,environmentId:$e)}",
    variables: {s: $s, e: $e}
  }')" >/dev/null
}

latest_status() { # latest_status <service-id> -> e.g. SUCCESS / FAILED / DEPLOYING
  gql "$(jq -n --arg s "$1" --arg e "$RAILWAY_ENVIRONMENT_ID" '{
    query: "query($s:String!,$e:String!){deployments(first:1,input:{serviceId:$s,environmentId:$e}){edges{node{status}}}}",
    variables: {s: $s, e: $e}
  }')" | jq -r '.data.deployments.edges[0].node.status // "UNKNOWN"'
}

wait_success() { # wait_success <service-id> <label>
  local deadline status
  deadline=$((SECONDS + WAIT_TIMEOUT_SECONDS))
  while ((SECONDS < deadline)); do
    status="$(latest_status "$1")"
    case "$status" in
      SUCCESS)
        echo "$2: deployment SUCCESS"
        return 0
        ;;
      FAILED | CRASHED | REMOVED)
        echo "$2: deployment $status — aborting rollout" >&2
        return 1
        ;;
      *)
        echo "$2: $status …"
        sleep "$POLL_SECONDS"
        ;;
    esac
  done
  echo "$2: timed out after ${WAIT_TIMEOUT_SECONDS}s — aborting rollout" >&2
  return 1
}

echo "Deploying ${IMAGE}"

echo "web: pinning image + deploying (pre-deploy migrate + /readyz gate run here)"
set_image "$RAILWAY_WEB_SERVICE_ID"
deploy "$RAILWAY_WEB_SERVICE_ID"
wait_success "$RAILWAY_WEB_SERVICE_ID" "web"

echo "worker: pinning image + deploying"
set_image "$RAILWAY_WORKER_SERVICE_ID"
deploy "$RAILWAY_WORKER_SERVICE_ID"

echo "beat: pinning image + deploying"
set_image "$RAILWAY_BEAT_SERVICE_ID"
deploy "$RAILWAY_BEAT_SERVICE_ID"

echo "Rollout of ${VERSION} triggered — web verified, worker/beat deploying."
