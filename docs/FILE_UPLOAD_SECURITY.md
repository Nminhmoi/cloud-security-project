# File upload security and lifecycle

CloudBox validates uploads before they reach local storage or S3. The current
no-cost controls include a 16 MiB request/file limit, a per-user storage quota,
extension and MIME allowlists, file signatures, Office container validation,
archive safety limits, SHA-256 checksums, private randomized storage keys, RBAC,
and a recoverable trash window.

## Configuration

The defaults can be changed with environment variables:

```dotenv
MAX_UPLOAD_BYTES=16777216
USER_STORAGE_QUOTA_BYTES=524288000
DELETED_DOCUMENT_RETENTION_DAYS=30
MAX_ARCHIVE_MEMBERS=1000
MAX_ARCHIVE_UNCOMPRESSED_BYTES=134217728
MAX_ARCHIVE_COMPRESSION_RATIO=100
```

The user quota counts both active and soft-deleted documents because both still
consume storage. Set `USER_STORAGE_QUOTA_BYTES=0` only when an unlimited quota
is explicitly intended.

## Metadata and object keys

`filename` is the sanitized user-facing name. `storage_key` is the private,
randomized location and is never returned by the document API. New uploads also
record the validated content type, byte size, SHA-256 checksum and scan status.
Existing database rows fall back to the legacy `filename` storage reference.

Apply the schema migration before deploying the new application revision:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml run --rm migrate
```

## Trash cleanup

Soft deletion records `deleted_at`; restoring a document clears it. Run this
command periodically to remove database rows and local/S3 objects after the
retention window:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml run --rm web `
  flask --app app.py purge-deleted-documents
```

For an immediate disposable-environment test, pass `--retention-days 0`. Do not
use zero retention in an environment where users expect trash recovery. S3
Versioning retains deleted object versions for the Terraform lifecycle window;
expired delete markers are cleaned automatically.

AWS instances created by this Terraform root module enable
`cloudbox-trash-purge.timer`, which runs the same command once per day. Check it
through Systems Manager Session Manager with:

```bash
systemctl status cloudbox-trash-purge.timer
journalctl -u cloudbox-trash-purge.service
```

## Malware scanning boundary

MIME, signatures and archive checks are structural validation, not malware
scanning. Before accepting untrusted public uploads in production, integrate an
asynchronous scanner and use `scan_status` values such as `pending`, `clean`,
`infected` and `failed`. Downloads must remain blocked until the result is
`clean`; the application already blocks `pending`, `infected` and `failed`
records. [GuardDuty Malware Protection for S3](https://docs.aws.amazon.com/guardduty/latest/ug/how-malware-protection-for-s3-gdu-works.html)
is a suitable AWS option, but it is not enabled by default because object
scanning is billable. With scanning disabled, new files use `not_scanned` and
remain downloadable after structural validation.
