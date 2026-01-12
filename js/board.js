// js/board.js
document.addEventListener('DOMContentLoaded', () => {
  let boardItems = [];

  const listEl   = document.getElementById('board-list');
  const tableEl  = document.getElementById('board-table-container');
  const detailEl = document.getElementById('board-detail');

  if (!listEl || !tableEl || !detailEl) {
    console.error('[board.js] Missing required elements: #board-list, #board-table-container, #board-detail');
    return;
  }

  // ------------------------------------------------------------
  // GitHub Pages pathing helpers (works for user pages + project pages)
  // ------------------------------------------------------------
  function repoBase() {
    // user pages:   https://user.github.io/         => base = ""
    // project pages:https://user.github.io/repo/... => base = "/repo"
    const parts = location.pathname.split('/').filter(Boolean);
    const isGithubIo = location.hostname.endsWith('github.io');
    return (isGithubIo && parts.length > 0) ? `/${parts[0]}` : '';
  }

  const BASE = repoBase();

  function urlFromRepo(path) {
    const clean = String(path || '').replace(/^\/+/, '');
    return encodeURI(`${BASE}/${clean}`);
  }

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"]/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'
    }[c]));
  }

  function basename(p) {
    const s = String(p || '');
    const last = s.split('/').pop();
    return last || s;
  }

  // ------------------------------------------------------------
  // Fetch helpers (with slightly better error messages)
  // ------------------------------------------------------------
  async function fetchText(url) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return await res.text();
  }

  async function fetchJson(url) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return await res.json();
  }

  // ------------------------------------------------------------
  // Load index
  // ------------------------------------------------------------
  fetchJson(urlFromRepo('data/posts.json'))
    .then(items => {
      boardItems = Array.isArray(items) ? items : [];
      renderList();
    })
    .catch(err => {
      console.error(err);
      tableEl.innerHTML = `
        <div class="alert alert-danger" role="alert">
          게시글 목록을 불러오지 못했습니다.<br>
          <code>${escapeHtml(err && err.message ? err.message : err)}</code>
        </div>
      `;
    });

  // ------------------------------------------------------------
  // Sorting: 공지 먼저, 그 다음 날짜 내림차순, 그 다음 id 내림차순
  // ------------------------------------------------------------
  function toDateValue(d) {
    // expects YYYY-MM-DD; fallback to 0
    const m = String(d || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return 0;
    const y = Number(m[1]), mo = Number(m[2]) - 1, da = Number(m[3]);
    const t = Date.UTC(y, mo, da);
    return Number.isFinite(t) ? t : 0;
  }

  function toNumericId(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function sortKey(item) {
    const pinned = (String(item?.notice || '').trim() === '공지') ? 0 : 1;
    const dateV  = -toDateValue(item?.date);
    const idNum  = toNumericId(item?.id);
    // If id is non-numeric, keep stable by string
    const idKey  = (idNum !== null) ? -idNum : String(item?.id ?? '');
    return { pinned, dateV, idNum, idKey };
  }

  function compareItems(a, b) {
    const ka = sortKey(a);
    const kb = sortKey(b);

    if (ka.pinned !== kb.pinned) return ka.pinned - kb.pinned;
    if (ka.dateV !== kb.dateV) return ka.dateV - kb.dateV;

    // both numeric ids
    if (ka.idNum !== null && kb.idNum !== null) return kb.idNum - ka.idNum;

    // fallback string compare (descending-ish)
    const sa = String(a?.id ?? '');
    const sb = String(b?.id ?? '');
    return sb.localeCompare(sa, 'ko');
  }

  // ------------------------------------------------------------
  // Render list
  // ------------------------------------------------------------
  function renderList() {
    const ordered = [...boardItems].sort(compareItems);

    const rows = ordered.map(item => {
      const idStr = String(item?.id ?? '');
      const isNotice = (String(item?.notice || '').trim() === '공지');

      return `
        <tr class="${isNotice ? 'table-secondary' : ''}">
          <td style="width:80px">${isNotice ? '공지' : escapeHtml(idStr)}</td>
          <td>
            <a href="#" class="board-link" data-id="${escapeHtml(idStr)}">
              ${escapeHtml(item?.title ?? '')}
            </a>
          </td>
          <td>${escapeHtml(item?.author ?? '')}</td>
          <td>${escapeHtml(item?.date ?? '')}</td>
        </tr>
      `;
    }).join('');

    tableEl.innerHTML = `
      <table class="table table-hover">
        <thead>
          <tr><th>번호</th><th>제목</th><th>작성자</th><th>등록일</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // ------------------------------------------------------------
  // Click handler
  // ------------------------------------------------------------
  tableEl.addEventListener('click', e => {
    const link = e.target.closest('.board-link');
    if (!link) return;
    e.preventDefault();

    const id = String(link.dataset.id ?? '');
    const item = boardItems.find(i => String(i?.id ?? '') === id);
    if (!item) return;

    showDetail(item);
  });

  // ------------------------------------------------------------
  // Detail view
  // ------------------------------------------------------------
  function normalizeContentfile(cfRaw) {
    // allow: "post.md", "data/posts/post.md", "/data/posts/post.md"
    return String(cfRaw || '')
      .replace(/^\/+/, '')
      .replace(/^data\/posts\/+/i, '');
  }

  function renderBody(text, cf) {
    const lower = String(cf || '').toLowerCase();
    if (lower.endsWith('.md')) {
      if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
        return marked.parse(text);
      }
      // marked not loaded: show raw
      return `<pre style="white-space:pre-wrap">${escapeHtml(text)}</pre>`;
    }
    // treat anything else as HTML fragment
    return text;
  }

  function renderAttachments(item) {
    const attachments = Array.isArray(item?.file_attachment) ? item.file_attachment : [];
    if (!attachments.length) return '';

    const links = attachments.map(f => {
      // support both: "data/files/a.pdf" OR {name, url}
      const url = (typeof f === 'string') ? f : (f && typeof f.url === 'string' ? f.url : '');
      if (!url) return '';

      const name = (typeof f === 'string')
        ? basename(url)
        : (f.name ? String(f.name) : basename(url));

      // attachment urls should also respect repo base; if url already starts with "http", keep it
      const href = /^https?:\/\//i.test(url) ? encodeURI(url) : urlFromRepo(url);

      return `<a href="${href}" target="_blank" rel="noopener">${escapeHtml(name)}</a>`;
    }).filter(Boolean).join('<br>');

    return links
      ? `<hr><p><strong>첨부파일:</strong><br>${links}</p>`
      : '';
  }

  function showDetail(item) {
    const cf = normalizeContentfile(item?.contentfile);
    if (!cf) {
      detailEl.innerHTML = `<p class="text-danger">contentfile이 비어있습니다.</p>`;
      listEl.style.display = 'none';
      detailEl.style.display = 'block';
      return;
    }

    const url = urlFromRepo(`data/posts/${cf}`);

    fetchText(url)
      .then(text => {
        const isNotice = (String(item?.notice || '').trim() === '공지');
        const idStr = String(item?.id ?? '');
        const bodyHtml = renderBody(text, cf);
        const filesHTML = renderAttachments(item);

        detailEl.innerHTML = `
          <table class="table table-hover mb-4">
            <thead>
              <tr>
                <th style="width:80px">번호</th>
                <th>제목</th>
                <th>작성자</th>
                <th>등록일</th>
              </tr>
            </thead>
            <tbody>
              <tr class="${isNotice ? 'table-secondary' : ''}">
                <td>${isNotice ? '공지' : escapeHtml(idStr)}</td>
                <td>${escapeHtml(item?.title ?? '')}</td>
                <td>${escapeHtml(item?.author ?? '')}</td>
                <td>${escapeHtml(item?.date ?? '')}</td>
              </tr>
            </tbody>
          </table>

          <div class="card mb-4"><div class="card-body">
            ${bodyHtml}
            ${filesHTML}
          </div></div>

          <button id="back-button" class="btn btn-secondary">← 목록으로</button>
        `;

        listEl.style.display   = 'none';
        detailEl.style.display = 'block';

        const backBtn = document.getElementById('back-button');
        if (backBtn) {
          backBtn.addEventListener('click', () => {
            detailEl.style.display = 'none';
            listEl.style.display   = 'block';
            window.scrollTo({ top: 0, behavior: 'smooth' });
          });
        }
      })
      .catch(err => {
        console.error(err);
        detailEl.innerHTML = `
          <div class="alert alert-danger" role="alert">
            <div>본문을 불러올 수 없습니다.</div>
            <div><code>${escapeHtml(err && err.message ? err.message : err)}</code></div>
            <div class="mt-2 small">요청 URL: <code>${escapeHtml(url)}</code></div>
          </div>
          <button id="back-button" class="btn btn-secondary">← 목록으로</button>
        `;

        listEl.style.display   = 'none';
        detailEl.style.display = 'block';

        const backBtn = document.getElementById('back-button');
        if (backBtn) {
          backBtn.addEventListener('click', () => {
            detailEl.style.display = 'none';
            listEl.style.display   = 'block';
            window.scrollTo({ top: 0, behavior: 'smooth' });
          });
        }
      });
  }
});
