# FK Cēsis Infrastructure

This repository owns deployed runtime for the FK Cēsis family of applications.

- FK Cēsis MMS deployment: `docs/fk-cesis-mms-deployment.md`
- Deployment security review, outstanding risks and rollout gates: [security maintenance](docs/deployment-security-review.md).
- Invoice Ninja currently uses inventory-selected Debian PHP-hotpatch images, not the historical Octane image: [build and identity verification](docs/invoiceninja-php-security-hotpatch.md).
- Routine daily backups are handled by the separate `server-backups` project and deferred here; one-off deployment recovery checkpoints remain in scope. The legacy backup role/cron has not been removed or changed.
# graphify-test
# graphify-auto-test
# test-auto
# manual-watcher-test
# graphify auto-update test
# graphify watch test
# graphify hook test
