# Model Deployment: FastAPI + Docker + AWS (End-to-End)

A minimal but complete example of taking a trained ML model from a Python
script to a containerized REST API running on AWS, deployed on the
**AWS Free Tier** (EC2 `t2.micro`/`t3.micro`).

**Stack:** scikit-learn → FastAPI → Docker → Amazon ECR → EC2 → GitHub Actions CI/CD

**Status:** ✅ Deployed and verified — live API, automated tests, and a fully
green CI/CD pipeline (test → build → push to ECR → deploy to EC2) confirmed
working end to end. See screenshots below.

## What's inside

```
.
├── train_model.py            # trains a RandomForest on the Iris dataset, saves it
├── model/
│   └── iris_model.joblib     # produced by train_model.py
├── app/
│   ├── main.py                # FastAPI app: /health, /predict, /predict/batch
│   └── schemas.py             # Pydantic request/response models
├── tests/
│   └── test_api.py            # pytest + FastAPI TestClient
├── .github/workflows/
│   └── ci-cd.yml               # test -> build -> push to ECR -> deploy to EC2 (SSH)
├── docs/screenshots/          # screenshots of the deployed API and pipeline
├── ec2-setup.sh               # one-time bootstrap script for a fresh EC2 instance
├── requirements.txt
├── Dockerfile
└── .dockerignore
```

The model itself (Iris classifier) is intentionally simple — the point of
this project is the *serving path*, not the ML. Swap in your own
`train_model.py` and it plugs into the same API/Docker/deploy pipeline.

## Screenshots

**Live API docs:**
![Swagger UI running live](docs/screenshots/swagger-ui-live.png)

**A real prediction response:**
![Successful prediction response](docs/screenshots/predict-response.png)

**EC2 instance running:**
![EC2 instance running](docs/screenshots/ec2-instance-running.png)

## 1. Run locally (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python train_model.py          # writes model/iris_model.joblib
fastapi dev app/main.py        # or: uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive Swagger UI.

Example request:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'
```

Run tests:

```bash
python -m pytest -v
```

## 2. Build and run with Docker

```bash
docker build -t iris-api:latest .
docker run -p 8000:8000 iris-api:latest
```

Visit http://127.0.0.1:8000/docs again — same API, now fully containerized.
The model file is baked into the image at build time (see comments in the
`Dockerfile` if you'd rather train inside the build).

## 3. AWS account setup (one time)

If you're starting from zero:

1. Sign up at aws.amazon.com/free (needs email, phone, and a card for
   identity verification — it won't be charged if you stay in free-tier
   limits). Pick the "Basic support - Free" plan.
2. Set a zero-spend budget alert: Billing → Budgets → Create budget →
   "Zero spend budget" template, add your email. This is your safety net.
3. Create an IAM admin user (don't use the root account day-to-day):
   IAM → Users → Create user → **Permissions tab → Add permissions → attach
   `AdministratorAccess`** (easy to forget this step — the user exists but
   can't do anything without it) → create an access key ("Command Line
   Interface (CLI)" use case). **Copy both values immediately** — the
   secret key is shown only once, and there is no way to retrieve it later
   if you lose it.
4. Install the AWS CLI locally, then run `aws configure` and paste in the
   access key, secret key, your region, and `json` output format.
5. Confirm it worked: `aws sts get-caller-identity` should print your
   account details.

## 4. Push the image to AWS ECR

```bash
# One-time: create the repository (free tier covers 500MB-month for 12 months)
aws ecr create-repository --repository-name iris-api --region <your-region>

# Authenticate Docker to your ECR registry
aws ecr get-login-password --region <your-region> \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<your-region>.amazonaws.com

# Tag and push
docker tag iris-api:latest <account-id>.dkr.ecr.<your-region>.amazonaws.com/iris-api:latest
docker push <account-id>.dkr.ecr.<your-region>.amazonaws.com/iris-api:latest
```

## 5. Launch the EC2 instance and deploy

1. **Launch:** EC2 → Launch instance → name it `iris-api-server` → AMI
   "Amazon Linux 2023" → instance type `t2.micro` or `t3.micro` (must be
   labeled **Free tier eligible**) → create a new key pair, download the
   `.pem` file, and **move it immediately to a permanent folder** (not
   Downloads) — it cannot be re-downloaded if lost.
2. **Security group — important:**
   - Port `8000` (Custom TCP) from **Anywhere (0.0.0.0/0)** — this is the
     API itself, needs to be public.
   - Port `22` (SSH) — if you only plan to deploy manually, "My IP" is
     safer. **But if you're using the GitHub Actions pipeline below, SSH
     must be open to Anywhere (0.0.0.0/0)**, because GitHub's runners
     connect from constantly-changing IPs, not a fixed one. This is a
     real trade-off (broader exposure to SSH scanning/brute-force
     attempts) — anyone attempting to connect still needs your private
     key, but the port itself is reachable. For a personal/learning
     project this is a common and acceptable trade-off; for anything more
     sensitive, look into restricting to GitHub's published runner IP
     ranges instead.
3. **Note the Public IPv4 address** once it's running — you'll need it
   below.
4. **Bootstrap Docker on the instance** using the included script:
   ```bash
   scp -i your-key.pem ec2-setup.sh ec2-user@<EC2_PUBLIC_IP>:~/
   ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP> "chmod +x ec2-setup.sh && ./ec2-setup.sh"
   ```
5. **First manual deploy** (later ones happen automatically via CI/CD):
   ```bash
   ssh -i your-key.pem ec2-user@<EC2_PUBLIC_IP>

   aws configure   # same access key/secret as your local setup, or a
                   # scoped-down IAM user — this lets the instance pull from ECR
   aws ecr get-login-password --region <your-region> \
     | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<your-region>.amazonaws.com
   docker pull <account-id>.dkr.ecr.<your-region>.amazonaws.com/iris-api:latest
   docker run -d --name iris-api --restart unless-stopped -p 8000:8000 \
     <account-id>.dkr.ecr.<your-region>.amazonaws.com/iris-api:latest
   ```
6. Visit `http://<EC2_PUBLIC_IP>:8000/docs` — that's your live API.

(Optional, once this is working: put Nginx or an ALB in front for a
domain name and TLS. Not required to get started.)

## 6. Latency optimization notes

These are the concrete choices already made in this codebase, worth
understanding rather than copying blindly:

- **Model loaded once at startup**, not per-request (`lifespan` in
  `app/main.py`). Reloading a joblib file on every call would dominate
  latency for a model this small.
- **Batch endpoint** (`/predict/batch`) scores N rows in a single call to
  the model instead of N separate HTTP round trips — the biggest lever for
  throughput-sensitive clients.
- **Multiple Uvicorn workers** (`--workers 2` in the Dockerfile CMD) so
  CPU-bound prediction calls on one request don't block another. A
  `t2.micro`/`t3.micro` has 1-2 vCPUs — keep worker count modest so you
  don't oversubscribe the instance.
- **Slim base image + layer caching** (`requirements.txt` copied and
  installed before app code) keeps builds fast and images small, which
  matters for pull time on a small instance and disk space on a
  free-tier volume.
- **`X-Process-Time-ms` response header** (added by middleware) gives you
  a free per-request latency signal in production without extra tooling —
  useful for spotting regressions after a deploy.
- For real workloads, next steps beyond this project would be: response
  caching for repeated inputs, moving to `onnxruntime` for faster inference
  if the model gets larger, and load testing with `locust` or `hey` to
  check the instance holds up under concurrent traffic.

## 7. CI/CD (GitHub Actions → ECR → EC2 via SSH)

`.github/workflows/ci-cd.yml` runs on every push/PR to `main`:

1. **`test` job** — installs deps, trains the model, runs `python -m pytest -v`.
   Runs on pull requests too, so broken code never reaches `main`. (Note:
   must be run as `python -m pytest`, not plain `pytest` — the module form
   adds the project root to Python's path so `from app.main import app`
   resolves correctly on GitHub's runners.)
2. **`build-and-deploy` job** (push to `main` only, after tests pass):
   - Builds the Docker image and pushes it to ECR, tagged with both the
     git SHA and `latest`.
   - SSHes into the EC2 instance and runs: `docker pull` the new image,
     stop/remove the old container, start the new one on port `8000`,
     then prune old images so a small free-tier disk doesn't fill up.

### One-time setup before this pipeline will run

You need sections 3-5 above done first (AWS account, ECR repo, EC2
instance with Docker installed via `ec2-setup.sh`, and SSH open to
0.0.0.0/0 as noted above). Then add these **repository secrets**
(Settings → Secrets and variables → Actions → New repository secret,
added **one at a time** — six separate secrets, not one combined value):

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Access key for a deploy IAM user |
| `AWS_SECRET_ACCESS_KEY` | Corresponding secret key |
| `AWS_REGION` | e.g. `ap-southeast-2` |
| `EC2_HOST` | The instance's Public IPv4 address |
| `EC2_USER` | `ec2-user` (default for Amazon Linux) |
| `EC2_SSH_KEY` | Full contents of the `.pem` key file, including the `-----BEGIN-----`/`-----END-----` lines |

The AWS deploy user needs at minimum `AmazonEC2ContainerRegistryPowerUser`
to push to ECR; the EC2 instance itself needs ECR *pull* access, either
via `aws configure` on the box (matches the manual step above) or, more
cleanly, by attaching an IAM instance role with `AmazonEC2ContainerRegistryReadOnly`
instead of storing credentials on the instance.

> **Note:** for a production setup, prefer OIDC
> (`aws-actions/configure-aws-credentials` supports `role-to-assume`) over
> long-lived access keys stored as secrets, and an IAM instance role over
> `aws configure` on the EC2 box. Static keys are used here to keep the
> first setup simple.

Once the secrets and EC2 instance exist, push to `main` and watch the
**Actions** tab — that's the whole pipeline running end to end.

## Lessons learned building this

A few real issues hit while building this, worth knowing if you hit them too:

- `pytest -v` alone fails with `ModuleNotFoundError: No module named 'app'`
  on GitHub's runners even though it works locally — use `python -m pytest -v`.
- If GitHub Actions' SSH deploy step times out with `dial tcp ***:22:
  i/o timeout`, it's almost always the security group blocking GitHub's
  IPs — SSH needs to be open to `0.0.0.0/0` for this pipeline to work.
- Secrets must be added as **separate named entries** — bundling
  everything into one secret value doesn't work; the workflow reads each
  one individually (`AWS_ACCESS_KEY_ID`, `AWS_REGION`, etc.).
- Save your `.pem` key file somewhere permanent immediately after
  downloading it — AWS never lets you download it again, and losing it
  means creating a new key pair and re-authorizing it on the instance.

## License

MIT — for the example code in this repository. FastAPI itself is licensed
separately under the MIT license by its authors.
