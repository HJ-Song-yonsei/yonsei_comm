# CMS and deployment security notes

## Sveltia CMS
- `admin/index.html` pins the CMS script to **0.253.2** and `admin/config.yml` pins its editor schema. Pinning stops unreviewed changes but does **not** automatically apply future security fixes.
- Review [Sveltia CMS releases](https://github.com/sveltia/sveltia-cms/releases) at least monthly and after security advisories. Update both versions together in a reviewed PR and test CMS login, post editing and attachments.
- Sveltia CMS access-token sign-in stores the GitHub PAT in the browser's local storage. Use a private, trusted browser profile, never a shared computer. Never put access tokens in the repository.
- Use a fine-grained PAT scoped only to `HJ-Song-yonsei/yonsei_comm` with **Contents: Read and write** (plus the default Metadata read). Only add **Pull requests: Read and write** if the editorial PR workflow is enabled. Require 2FA, set token expiration, and revoke exposed tokens.
- The public `/admin/` URL itself does not grant editing access; GitHub permissions protect content changes.

## GitHub Actions
- Trusted GitHub Actions are pinned to exact released commit SHAs. Weekly Dependabot updates should be reviewed before merge.
- The Pages build job has only `contents: read` and checkout credentials are not persisted; only the deploy job can request `pages: write` and `id-token: write`.
- The Pages artifact includes `.nojekyll`. Other dotfiles are excluded when building and rejected by an extra validation step.
- Pure and FIS update jobs retain `contents: write` because they automatically commit regenerated JSON to `main`. Check these scheduled jobs after upgrading Actions.

## Node.js dependency
The removed root `package.json` declared `fast-xml-parser`, but the repository has no npm build or Node.js server and no Node.js scripts using it. Re-add a manifest with a lockfile and security scans only if a future Node.js build is introduced.

## Post-merge checks
1. Verify GitHub Pages build and deploy jobs succeed.
2. Check CMS login, entry editing and attachment upload with a permitted account.
3. Check Korean and English navigation, posts, curricula, and attachments.
4. Observe or dispatch the next Pure and FIS data refresh workflows.
