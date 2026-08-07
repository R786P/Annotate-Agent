const chatMessages = document.getElementById('chatMessages');
const composerForm = document.getElementById('composerForm');
const textInput = document.getElementById('textInput');
const videoInput = document.getElementById('videoInput');
const attachBtn = document.getElementById('attachBtn');
const fileChip = document.getElementById('fileChip');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');

let selectedFile = null;

attachBtn.addEventListener('click', () => videoInput.click());

videoInput.addEventListener('change', () => {
  if (videoInput.files.length > 0) {
    selectedFile = videoInput.files[0];
    fileChip.textContent = '📎 ' + selectedFile.name;
    fileChip.classList.remove('hidden');
  }
});

newChatBtn.addEventListener('click', () => {
  chatMessages.innerHTML = `
    <div class="msg msg-bot">
      <div class="bubble">👋 Video bhejo aur batao kya karna hai. Main video dekh ke draft segments bana dunga.</div>
    </div>`;
  selectedFile = null;
  fileChip.classList.add('hidden');
  textInput.value = '';
});

textInput.addEventListener('input', () => {
  textInput.style.height = 'auto';
  textInput.style.height = Math.min(textInput.scrollHeight, 100) + 'px';
});

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addUserMessage(text, fileName) {
  const div = document.createElement('div');
  div.className = 'msg msg-user';
  div.innerHTML = `
    <div class="bubble">
      ${fileName ? `<div class="video-chip-inline">📎 ${fileName}</div><br>` : ''}
      ${text}
    </div>`;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function addBotBubble(contentHtml, extraClass = '') {
  const div = document.createElement('div');
  div.className = 'msg msg-bot';
  div.innerHTML = `<div class="bubble ${extraClass}">${contentHtml}</div>`;
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function segmentsToTable(segments) {
  let rows = segments.map(seg => `
    <tr>
      <td>${seg.start_fmt}</td>
      <td>${seg.end_fmt}</td>
      <td>${seg.label || ''}</td>
      <td>${seg.reason || ''}</td>
    </tr>`).join('');
  return `
    <div>${segments.length} segments mile:</div>
    <table class="seg-table">
      <thead><tr><th>Start</th><th>End</th><th>Label</th><th>Reason</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

composerForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const instructions = textInput.value.trim();

  if (!selectedFile) {
    addBotBubble('⚠️ Pehle video attach karo (📎 icon dabao).', 'error');
    return;
  }
  if (!instructions) {
    addBotBubble('⚠️ Instructions likho ki kya karna hai.', 'error');
    return;
  }

  addUserMessage(instructions, selectedFile.name);

  const formData = new FormData();
  formData.append('video', selectedFile);
  formData.append('instructions', instructions);

  textInput.value = '';
  textInput.style.height = 'auto';
  sendBtn.disabled = true;

  const loadingBubble = addBotBubble('⏳ Video analyze ho raha hai, thoda time lagega...', 'loading');

  try {
    const res = await fetch('/analyze', { method: 'POST', body: formData });

    let data;
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      data = await res.json();
    } else {
      const text = await res.text();
      throw new Error(`Server error (status ${res.status}): ${text.slice(0, 200)}`);
    }

    if (!res.ok) {
      throw new Error(data.error || 'Kuch galat ho gaya.');
    }

    loadingBubble.remove();
    addBotBubble(segmentsToTable(data.segments));

  } catch (err) {
    loadingBubble.remove();
    addBotBubble('❌ ' + err.message, 'error');
  } finally {
    sendBtn.disabled = false;
    selectedFile = null;
    fileChip.classList.add('hidden');
    videoInput.value = '';
  }
});
