"""Upload a dated snapshot of this project to Cloudflare R2.

Run from PyCharm's terminal:
    .venv312/bin/python push_snapshot_to_r2.py

Reads credentials from r2.env. The archive leaves out r2.env, other .env
files, virtual environments, IDE settings and caches. It keeps the
person-level and raw data, because R2 is where those belong.
"""
import datetime
import os
import pathlib
import tarfile

import boto3

ROOT = pathlib.Path(__file__).resolve().parent
SKIP_DIRS = {".venv", ".venv312", "venv", ".idea", "__pycache__", ".git", "node_modules"}
SKIP_NAMES = {"r2.env", ".DS_Store"}


def load_env(path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.replace("export ", "").strip()
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def keep(path):
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIRS or part.startswith(".venv") for part in rel.parts):
        return False
    name = rel.name
    if name in SKIP_NAMES or name.endswith(".env"):
        return False
    if name.endswith(".tar.gz") and (name.startswith("_github_push_") or name.startswith("AnthropicBiasData_")):
        return False
    return path.is_file()


def main():
    load_env(ROOT / "r2.env")
    stamp = datetime.date.today().isoformat()
    archive = ROOT.parent / f"AnthropicBiasData_{stamp}.tar.gz"

    files = sorted(p for p in ROOT.rglob("*") if keep(p))
    print(f"Packing {len(files)} files into {archive.name} ...")
    with tarfile.open(archive, "w:gz") as tar:
        for p in files:
            tar.add(p, arcname=f"AnthropicBiasData/{p.relative_to(ROOT)}")
    size = archive.stat().st_size
    print(f"Archive size: {size / 1e6:.1f} MB")

    bucket = os.environ["R2_BUCKET"]
    key = f"snapshots/{stamp}/{archive.name}"
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        region_name="auto",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    print(f"Uploading to r2://{bucket}/{key} ...")
    s3.upload_file(str(archive), bucket, key)

    remote = s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
    if remote != size:
        raise SystemExit(f"FAILED: R2 has {remote} bytes, local has {size} bytes")
    print(f"DONE: r2://{bucket}/{key} verified ({remote} bytes)")


if __name__ == "__main__":
    main()
