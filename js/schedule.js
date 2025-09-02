// js/schedule.js
document.addEventListener('DOMContentLoaded', () => {
  fetch('/api/schedule')
    .then(res => {
      if (!res.ok) throw new Error(res.statusText);
      return res.text();
    })
    .then(html => {
      document.getElementById('sche-container').innerHTML = html;
    })
    .catch(err => {
      console.error('스케줄 로드 실패:', err);
      document.getElementById('sche-container')
              .innerHTML = '<p class="text-danger">일정 정보를 불러오는 데 실패했습니다.</p>';
    });
});