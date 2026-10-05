# Korean / English site build

The Korean root pages remain the structural and visual source of truth. During deployment, the bilingual build creates a static English mirror under `/en/` while preserving the Korean layout, Bootstrap structure, shared CSS/JavaScript, and production image assets.

## Required GitHub secret

Add one repository Actions secret named exactly:

`DEEPL_API_KEY`

See `i18n/DEEPL_SETUP.md` for setup steps. The key is used only during build time and is never exposed to browser JavaScript.

## English scope

Generated for production:

- Home / department introduction
- Current faculty
- Professor emeriti / former faculty
- Undergraduate and graduate curriculum
- Scholarships
- Research overview and four research-area pages
- Research Centers
- Yonsei–UvA and Yonsei–CityU pages

Intentionally omitted from English:

- Academic notices (`notice.html`)
- Competition/recruitment notices (`jobnotice.html`)
- Equipment rental (`lend.html`)
- Adjunct / affiliated faculty (`people_profpractice.html`)

## Translation pipeline

1. `scripts/prepare_korean_site.py` prepares the Korean deployment output and replaces the legacy translation widget with a direct `EN` toggle.
2. `scripts/build_english_site.py` translates the core English pages and research JSON feeds with DeepL.
3. `scripts/build_additional_english_pages.py` builds the professor emeriti / former faculty English page.
4. `scripts/postprocess_english_site.py` applies official names, roles, terminology, English/KO toggles, and deterministic navigation.
5. `scripts/refine_english_site.py` applies approved homepage wording and Directions/facility labels.
6. `scripts/verify_i18n_build.py` fails the build if the bilingual deployment contract is broken.

## Terminology

Confirmed terminology is stored in `i18n/glossary_ko-en.tsv` and additionally enforced by deterministic post-processing where context matters (for example Dean vs. individual JMC Program Chair titles).

## Translation cache

GitHub Actions caches translated source strings in `.i18n-cache/en.json`. Unchanged Korean strings are reused on later builds, which reduces repeated DeepL usage.

## Assets and layout

English pages are generated from the Korean HTML and retain the same layout, component structure, and shared assets. English-only CSS is deliberately limited to typography fitting, dropdown wrapping, and the direct language toggle.

## Language switching

Google Translate is not used. The production site exposes a direct two-language switch:

- Korean page: `EN ▾`
- English page: `KO ▾`

Same-page counterparts are used whenever an English page exists. Korean-only notice/equipment pages fall back to the English homepage.

## Local full build

With `DEEPL_API_KEY` exported:

```bash
bash scripts/build_local_bilingual.sh
python3 -m http.server 8000 --directory build
```

Then open `http://localhost:8000/` and `http://localhost:8000/en/`.
