document.addEventListener('DOMContentLoaded', () => {
  let boardItems = [];

  const listEl   = document.getElementById('board-list');
  const tableEl  = document.getElementById('board-table-container');
  const detailEl = document.getElementById('board-detail');

  fetch('/data/posts.json')
    .then(r => r.json())
    .then(items => {
      boardItems = items;
      renderList();
    })
    .catch(console.error);

  function renderList() {
    const notices = boardItems.filter(i => i.notice === '공지');
    const normals = boardItems.filter(i => i.notice !== '공지')
                              .sort((a,b) => b.id - a.id);
    const ordered = [...notices, ...normals];

    const rows = ordered.map(item => `
      <tr class="${item.notice === '공지' ? 'table-secondary' : ''}">
        <td style="width:80px">${item.notice === '공지' ? '공지' : item.id}</td>
        <td><a href="#" class="board-link" data-id="${item.id}">${item.title}</a></td>
        <td>${item.author}</td>
        <td>${item.date}</td>
      </tr>
    `).join('');

    tableEl.innerHTML = `
      <table class="table table-hover">
        <thead>
          <tr><th>번호</th><th>제목</th><th>작성자</th><th>등록일</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  tableEl.addEventListener('click', e => {
    const link = e.target.closest('.board-link');
    if (!link) return;
    e.preventDefault();

    const id = Number(link.dataset.id);
    const item = boardItems.find(i => i.id === id);
    if (!item) return;

    showDetail(item);
  });

  function showDetail(item) {
    fetch(`/data/posts/${item.contentfile}`)
      .then(r => r.text())
      .then(html => {
        const attachments = item.file_attachment || [];

        const filesHTML = attachments.length
          ? `<hr><p><strong>첨부파일:</strong><br>
              ${attachments.map(f =>
                `<a href="${f}" target="_blank">${f.split('/').pop()}</a>`
              ).join('<br>')}
             </p>`
          : '';

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
              <tr class="${item.notice === '공지' ? 'table-secondary' : ''}">
                <td>${item.notice === '공지' ? '공지' : item.id}</td>
                <td>${item.title}</td>
                <td>${item.author}</td>
                <td>${item.date}</td>
              </tr>
            </tbody>
          </table>

          <div class="card mb-4"><div class="card-body">
            ${html}
            ${filesHTML}
          </div></div>

          <button id="back-button" class="btn btn-secondary">← 목록으로</button>
        `;

        listEl.style.display   = 'none';
        detailEl.style.display = 'block';

        document.getElementById('back-button')
          .addEventListener('click', () => {
            detailEl.style.display = 'none';
            listEl.style.display   = 'block';
            window.scrollTo({ top: 0, behavior: 'smooth' });
          });
      })
      .catch(err => {
        detailEl.innerHTML = `<p class="text-danger">본문을 불러올 수 없습니다.</p>`;
      });
  }
});
