# English site build

The Korean root pages remain the structural source of truth. On deployment, `scripts/build_english_site.py` generates a static English mirror under `/en/` using DeepL.

## Required GitHub secret

Add a repository Actions secret named:

`DEEPL_API_KEY`

The key is read only by GitHub Actions. It is never shipped to browser JavaScript or committed to the repository.

## English scope

Generated in the first production phase:

- Home / department introduction
- Current faculty
- Undergraduate and graduate curriculum
- Scholarships
- Research overview and four research-area pages
- Research institutes/centers
- Yonsei–UvA and Yonsei–CityU pages

Intentionally omitted from English:

- Academic notices (`notice.html`)
- Competition/recruitment notices (`jobnotice.html`)
- Equipment rental (`lend.html`)
- Emeritus/retired faculty and adjunct/practice faculty pending official English-name/title review

## Terminology

Confirmed official terms are stored in `i18n/glossary_ko-en.tsv` and also enforced by the build script before DeepL translation. These overrides take precedence over machine translation.

## Translation cache

GitHub Actions caches translated source strings in `.i18n-cache/en.json`. Unchanged Korean strings are reused on subsequent deployments; only new/changed strings are sent to DeepL.

## Assets and layout

English pages are generated directly from the Korean HTML and retain the same markup, Bootstrap classes, CSS, JavaScript and image assets. English pages reference shared root assets using `../css`, `../js`, `../images`, and so on; images are not duplicated.

## Language switching

`js/langswitcher.js` treats English as a dedicated static site:

- Korean → English: `/page.html` → `/en/page.html`
- English → Korean: `/en/page.html` → `/page.html`
- Japanese and Simplified Chinese continue to use the existing Google Translate widget on the Korean source page until dedicated static builds are added.
