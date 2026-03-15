# tty-theme — Production Deploy Guide

**These commands deploy real GCP infrastructure. Do NOT run during local development.**

---

## Prerequisites

```bash
gcloud auth login
gcloud config set project tinkerwithtech-214914
```

---

## Service Account (least privilege)

```bash
gcloud iam service-accounts create tty-theme-api \
  --display-name="tty-theme API"

# Grant only what's needed — no owner/editor roles
gcloud projects add-iam-policy-binding tinkerwithtech-214914 \
  --member="serviceAccount:tty-theme-api@tinkerwithtech-214914.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding tinkerwithtech-214914 \
  --member="serviceAccount:tty-theme-api@tinkerwithtech-214914.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding tinkerwithtech-214914 \
  --member="serviceAccount:tty-theme-api@tinkerwithtech-214914.iam.gserviceaccount.com" \
  --role="roles/monitoring.metricWriter"
```

---

## Secret Manager — Create Secrets

```bash
echo -n "your-gemini-key" | gcloud secrets create GEMINI_API_KEY --data-file=-
echo -n "your-github-client-id" | gcloud secrets create GITHUB_CLIENT_ID --data-file=-
echo -n "your-github-client-secret" | gcloud secrets create GITHUB_CLIENT_SECRET --data-file=-
```

---

## Build & Push Docker Image

```bash
docker build -t gcr.io/tinkerwithtech-214914/tty-theme-api:latest .
docker push gcr.io/tinkerwithtech-214914/tty-theme-api:latest
```

---

## Deploy to Cloud Run

```bash
gcloud run deploy tty-theme-api \
  --image=gcr.io/tinkerwithtech-214914/tty-theme-api:latest \
  --region=us-central1 \
  --project=tinkerwithtech-214914 \
  --min-instances=0 \
  --max-instances=10 \
  --memory=256Mi \
  --concurrency=80 \
  --service-account=tty-theme-api@tinkerwithtech-214914.iam.gserviceaccount.com \
  --set-env-vars=ENVIRONMENT=production,GCP_PROJECT=tinkerwithtech-214914,FIRESTORE_PROJECT=tinkerwithtech-214914 \
  --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --set-secrets=GITHUB_CLIENT_ID=GITHUB_CLIENT_ID:latest \
  --set-secrets=GITHUB_CLIENT_SECRET=GITHUB_CLIENT_SECRET:latest \
  --no-allow-unauthenticated
```

---

## Deploy Web UI (Firebase Hosting)

```bash
cd web && npm run build
firebase deploy --only hosting --project tinkerwithtech-214914
```

---

## Custom Domain

```bash
# Verify domain ownership first at console.firebase.google.com
firebase hosting:channel:deploy production --project tinkerwithtech-214914
```

---

## Cloud Monitoring Alerts

```bash
# p99 latency > 5s
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="tty-theme API p99 latency" \
  --condition-display-name="p99 > 5s" \
  --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_latencies"' \
  --condition-threshold-value=5000 \
  --condition-threshold-comparison=COMPARISON_GT \
  --condition-aggregation-per-series-aligner=ALIGN_PERCENTILE_99

# Error rate > 5% (set up similarly in Cloud Console)
```

---

## Firestore Indexes

Deployed automatically via `firestore.indexes.json`:
```bash
firebase deploy --only firestore:indexes --project tinkerwithtech-214914
```

---

## Rollback

```bash
# List previous revisions
gcloud run revisions list --service=tty-theme-api --region=us-central1

# Route 100% traffic to a previous revision
gcloud run services update-traffic tty-theme-api \
  --to-revisions=tty-theme-api-00042-abc=100 \
  --region=us-central1
```
