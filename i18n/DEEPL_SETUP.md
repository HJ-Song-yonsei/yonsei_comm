# DeepL API setup for the English site

The English site is translated at **build time in GitHub Actions**. The DeepL key is never shipped to the browser or committed to the repository.

## 1. Create a DeepL API key

1. Sign in to the DeepL account that will own the translation usage.
2. Make sure the account has a DeepL **API** plan (not only the web/desktop translator plan).
3. Open **Account → API Keys & Limits**.
4. Create a key. A descriptive name such as `yonsei-comm-github-actions` is recommended.
5. Copy the full key once it is created.
6. Optional but recommended: configure a key-level usage limit / cost-control limit in DeepL.

## 2. Store the key in GitHub Actions

In `HJ-Song-yonsei/yonsei_comm`:

1. Open **Settings**.
2. Open **Secrets and variables → Actions**.
3. Choose **New repository secret**.
4. Name the secret exactly:

   `DEEPL_API_KEY`

5. Paste the DeepL API key as the value and save it.

Do **not** add the key to JavaScript, HTML, `.env` files committed to Git, workflow YAML, or any public config file.

## 3. What happens during deployment

The Pages workflow will:

1. Validate that `DEEPL_API_KEY` exists.
2. Assemble the Korean static site into `build/` and replace the legacy Google Translate UI with the direct `EN` toggle.
3. Generate `/en/` from the Korean source HTML with DeepL.
4. Generate English research JSON feeds.
5. Apply the department's fixed terminology, official faculty names/roles, homepage wording, and English-only layout adjustments.
6. Run `scripts/verify_i18n_build.py`.
7. Deploy only when the workflow is running on `main` (pull requests build and validate but do not deploy).

## 4. Translation cache

`.i18n-cache/en.json` is restored through GitHub Actions cache. Unchanged Korean strings can therefore reuse previous translations instead of being retransmitted to DeepL on every deployment.

The cache is **not** committed to the repository and contains translated text, not the API key.

## 5. Optional local full build

After exporting the key in the shell:

```bash
export DEEPL_API_KEY='YOUR_KEY_HERE'
bash scripts/build_local_bilingual.sh
```

Then preview the generated deployment tree with:

```bash
python3 -m http.server 8000 --directory build
```

Open:

- Korean: `http://localhost:8000/`
- English: `http://localhost:8000/en/`

## 6. If a key is ever exposed

Deactivate the exposed key in DeepL **API Keys & Limits**, create a replacement, and update the GitHub `DEEPL_API_KEY` repository secret.
