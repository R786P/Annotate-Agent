const chatMessages = document.getElementById('chatMessages');
const composerForm = document.getElementById('composerForm');
const textInput = document.getElementById('textInput');
const videoInput = document.getElementById('videoInput');
const attachBtn = document.getElementById('attachBtn');
const fileChip = document.getElementById('fileChip');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');

// Live Screen feature
const liveScreenBtn = document.getElementById('liveScreenBtn');
const stopLiveScreenBtn = document.getElementById('stopLiveScreenBtn');
const liveScreenPanel = document.getElementById('liveScreenPanel');
const liveScreenPreview = document.getElementById('liveScreenPreview');
const liveScreenStatus = document.getElementById('liveScreenStatus');
const liveStatus = document.getElementById('liveStatus');

let selectedFile = null;

// Live Screen state
let liveSocket = null;
let screenStream = null;
let liveCanvas = null;
let liveContext = null;
let liveFrameTimer = null;
let liveConnected = false;

attachBtn.addEventListener('click', () => videoInput.click());

videoInput.addEventListener('change', () => {
  if (videoInput.files.length > 0) {
    selectedFile = videoInput.files[0];
    fileChip.textContent = '📎 ' + selectedFile.name;
    fileChip.classList.remove('hidden');
  }
});

newChatBtn.addEventListener('click', () => {
  stopLiveScreen();
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

  // In Live Screen mode, the same composer becomes the live chat input.
  if (liveConnected) {
    if (!instructions) return;
    addUserMessage(instructions);
    sendLiveText(instructions);
    textInput.value = '';
    textInput.style.height = 'auto';
    return;
  }

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

// =========================================================
// LIVE SCREEN FEATURE
// =========================================================

if (liveScreenBtn) {
  liveScreenBtn.addEventListener('click', startLiveScreen);
}

if (stopLiveScreenBtn) {
  stopLiveScreenBtn.addEventListener('click', stopLiveScreen);
}

async function startLiveScreen() {
  if (liveConnected) return;

  if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
    addBotBubble('❌ Is browser me screen sharing supported nahi hai.', 'error');
    return;
  }

  try {
    liveScreenBtn.disabled = true;
    liveScreenBtn.textContent = '⏳ Connecting...';
    liveScreenStatus.textContent = 'Secure Live session prepare ho raha hai...';

    // API key browser me expose nahi hoti. Backend short-lived token deta hai.
    const tokenResponse = await fetch('/live-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    const tokenData = await tokenResponse.json();

    if (!tokenResponse.ok) {
      throw new Error(tokenData.error || 'Live token create nahi hua.');
    }

    // Browser native screen picker.
    screenStream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: { ideal: 5, max: 8 } },
      audio: false
    });

    liveScreenPreview.srcObject = screenStream;

    liveCanvas = document.createElement('canvas');
    liveContext = liveCanvas.getContext('2d', { alpha: false });

    const wsUrl =
      'wss://generativelanguage.googleapis.com/ws/' +
      'google.ai.generativelanguage.v1beta.' +
      'GenerativeService.BidiGenerateContentConstrained' +
      '?access_token=' + encodeURIComponent(tokenData.token);

    liveSocket = new WebSocket(wsUrl);

    liveSocket.onopen = () => {
      liveSocket.send(JSON.stringify({
        setup: {
          model: `models/${tokenData.model}`,
          responseModalities: ['TEXT'],
          systemInstruction: {
            parts: [{
              text: 'Tum Annotate Agent ho. User ki shared screen ko samjho aur visible UI, errors, buttons aur content ke baare me Hindi/Hinglish me concise jawab do. Screen par visible password, API key, token ya other sensitive secret ko kabhi repeat mat karo.'
            }]
          }
        }
      }));

      liveConnected = true;
      liveStatus.textContent = '● LIVE';
      liveStatus.classList.add('active');
      liveScreenPanel.classList.remove('hidden');
      liveScreenBtn.textContent = '🟢 Live Active';
      liveScreenStatus.textContent = 'Screen Gemini ko live bheji ja rahi hai...';

      addBotBubble('🟢 Live Screen connected. Ab screen ke baare me pooch sakte ho.');
      startLiveFrameCapture();
    };

    liveSocket.onmessage = handleLiveMessage;

    liveSocket.onerror = () => {
      addBotBubble('❌ Gemini Live connection error.', 'error');
    };

    liveSocket.onclose = () => {
      if (liveConnected) {
        addBotBubble('⚠️ Live connection close ho gaya.', 'error');
      }
      cleanupLiveScreen();
    };

    const track = screenStream.getVideoTracks()[0];
    if (track) {
      track.addEventListener('ended', stopLiveScreen, { once: true });
    }

  } catch (err) {
    console.error(err);
    addBotBubble('❌ Live Screen start nahi hua: ' + err.message, 'error');
    cleanupLiveScreen();
  }
}

function startLiveFrameCapture() {
  stopLiveFrameCapture();
  liveFrameTimer = setInterval(captureAndSendLiveFrame, 1000);
  captureAndSendLiveFrame();
}

function stopLiveFrameCapture() {
  if (liveFrameTimer) {
    clearInterval(liveFrameTimer);
    liveFrameTimer = null;
  }
}

function captureAndSendLiveFrame() {
  if (!liveConnected || !liveSocket || liveSocket.readyState !== WebSocket.OPEN) return;
  if (!liveScreenPreview.videoWidth || !liveScreenPreview.videoHeight) return;

  const maxWidth = 1280;
  const sourceWidth = liveScreenPreview.videoWidth;
  const sourceHeight = liveScreenPreview.videoHeight;
  const scale = Math.min(1, maxWidth / sourceWidth);

  liveCanvas.width = Math.round(sourceWidth * scale);
  liveCanvas.height = Math.round(sourceHeight * scale);

  liveContext.drawImage(liveScreenPreview, 0, 0, liveCanvas.width, liveCanvas.height);

  const jpeg = liveCanvas.toDataURL('image/jpeg', 0.65);
  const base64Data = jpeg.split(',')[1];

  try {
    liveSocket.send(JSON.stringify({
      realtimeInput: {
        video: {
          data: base64Data,
          mimeType: 'image/jpeg'
        }
      }
    }));
  } catch (err) {
    console.error('Live frame send error:', err);
  }
}

function sendLiveText(text) {
  if (!liveSocket || liveSocket.readyState !== WebSocket.OPEN) {
    addBotBubble('⚠️ Live connection available nahi hai.', 'error');
    return;
  }

  liveSocket.send(JSON.stringify({
    clientContent: {
      turns: [{
        role: 'user',
        parts: [{ text }]
      }],
      turnComplete: true
    }
  }));
}

function handleLiveMessage(event) {
  try {
    const response = JSON.parse(event.data);

    if (response.setupComplete) {
      liveScreenStatus.textContent = 'Gemini Live ready — screen observe ho rahi hai.';
    }

    const serverContent = response.serverContent;
    if (!serverContent || !serverContent.modelTurn) return;

    const parts = serverContent.modelTurn.parts || [];
    for (const part of parts) {
      if (part.text) addBotBubble(part.text);
    }
  } catch (err) {
    console.error('Live response parse error:', err);
  }
}

function stopLiveScreen() {
  stopLiveFrameCapture();

  if (liveSocket) {
    try { liveSocket.close(); } catch (e) {}
    liveSocket = null;
  }

  if (screenStream) {
    screenStream.getTracks().forEach(track => track.stop());
    screenStream = null;
  }

  cleanupLiveScreen();
}

function cleanupLiveScreen() {
  stopLiveFrameCapture();
  liveConnected = false;

  if (liveStatus) {
    liveStatus.textContent = 'Offline';
    liveStatus.classList.remove('active');
  }

  if (liveScreenPanel) liveScreenPanel.classList.add('hidden');

  if (liveScreenBtn) {
    liveScreenBtn.disabled = false;
    liveScreenBtn.textContent = '🔴 Live Screen';
  }

  if (liveScreenStatus) liveScreenStatus.textContent = 'Screen share start nahi hua.';
  if (liveScreenPreview) liveScreenPreview.srcObject = null;
}
