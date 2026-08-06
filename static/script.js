const form = document.getElementById('analyzeForm');
const loading = document.getElementById('loading');
const errorBox = document.getElementById('error');
const results = document.getElementById('results');
const resultsBody = document.getElementById('resultsBody');
const metaInfo = document.getElementById('metaInfo');
const submitBtn = document.getElementById('submitBtn');

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  errorBox.classList.add('hidden');
  results.classList.add('hidden');
  loading.classList.remove('hidden');
  submitBtn.disabled = true;

  const formData = new FormData(form);

  try {
    const res = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || 'Kuch galat ho gaya.');
    }

    metaInfo.textContent = `${data.frames_analyzed} frames analyze kiye, video ~${Math.round(data.duration)}s`;
    resultsBody.innerHTML = '';
    data.segments.forEach(seg => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${seg.start_fmt}</td>
        <td>${seg.end_fmt}</td>
        <td>${seg.label || ''}</td>
        <td>${seg.reason || ''}</td>
      `;
      resultsBody.appendChild(tr);
    });

    results.classList.remove('hidden');
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.classList.remove('hidden');
  } finally {
    loading.classList.add('hidden');
    submitBtn.disabled = false;
  }
});
