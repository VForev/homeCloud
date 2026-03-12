const state = {
  messages: [],
  models: [],
  imageBase64: null,
  imageMime: null,
  imageName: null,
  imagePreviewUrl: null,
  imageWidth: null,
  imageHeight: null,
  busy: false
};

const el = {
  status: document.getElementById('status'),
  chatMeta: document.getElementById('chatMeta'),
  model: document.getElementById('model'),
  temperature: document.getElementById('temperature'),
  numPredict: document.getElementById('numPredict'),
  refreshBtn: document.getElementById('refreshBtn'),
  clearBtn: document.getElementById('clearBtn'),
  chat: document.getElementById('chat'),
  empty: document.getElementById('empty'),
  composer: document.getElementById('composer'),
  prompt: document.getElementById('prompt'),
  promptCount: document.getElementById('promptCount'),
  sendBtn: document.getElementById('sendBtn'),
  imageInput: document.getElementById('imageInput'),
  attachmentBadge: document.getElementById('attachmentBadge'),
  fileInfo: document.getElementById('fileInfo'),
  removeImageBtn: document.getElementById('removeImageBtn'),
  imagePreview: document.getElementById('imagePreview')
};

function setStatus(text, tone = 'neutral') {
  el.status.textContent = text;
  el.status.classList.remove('busy', 'ok', 'error');
  if (tone === 'busy') el.status.classList.add('busy');
  if (tone === 'ok') el.status.classList.add('ok');
  if (tone === 'error') el.status.classList.add('error');
}

function setBusy(isBusy) {
  state.busy = isBusy;
  el.sendBtn.disabled = isBusy;
  el.sendBtn.textContent = isBusy ? 'Sending...' : 'Send';
}

function updatePromptCount() {
  if (!el.promptCount) return;
  el.promptCount.textContent = `${el.prompt.value.length} chars`;
}

function updateChatMeta() {
  if (!el.chatMeta) return;
  el.chatMeta.textContent = `${state.messages.length} message${state.messages.length === 1 ? '' : 's'}`;
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderMarkdown(text) {
  const escaped = escapeHtml(text);
  const codeBlocks = [];
  let temp = escaped.replace(/```([\s\S]*?)```/g, (_, code) => {
    const key = `__CODEBLOCK_${codeBlocks.length}__`;
    codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`);
    return key;
  });

  temp = temp
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');

  const lines = temp.split('\n');
  const html = [];
  let inUl = false;
  let inOl = false;

  function closeLists() {
    if (inUl) {
      html.push('</ul>');
      inUl = false;
    }
    if (inOl) {
      html.push('</ol>');
      inOl = false;
    }
  }

  for (const line of lines) {
    if (/^[-*]\s+/.test(line)) {
      if (inOl) {
        html.push('</ol>');
        inOl = false;
      }
      if (!inUl) {
        html.push('<ul>');
        inUl = true;
      }
      html.push(`<li>${line.replace(/^[-*]\s+/, '')}</li>`);
    } else if (/^\d+\.\s+/.test(line)) {
      if (inUl) {
        html.push('</ul>');
        inUl = false;
      }
      if (!inOl) {
        html.push('<ol>');
        inOl = true;
      }
      html.push(`<li>${line.replace(/^\d+\.\s+/, '')}</li>`);
    } else {
      closeLists();
      if (line.trim() === '') {
        html.push('');
      } else if (/^<h[1-3]>/.test(line) || /^<pre>/.test(line)) {
        html.push(line);
      } else {
        html.push(`<p>${line}</p>`);
      }
    }
  }
  closeLists();

  let finalHtml = html.join('');
  codeBlocks.forEach((block, index) => {
    finalHtml = finalHtml.replace(`__CODEBLOCK_${index}__`, block);
  });
  return finalHtml;
}

function createAssistantActions(messageText) {
  const actions = document.createElement('div');
  actions.className = 'assistant-actions';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'chip-btn';
  copyBtn.type = 'button';
  copyBtn.textContent = 'Copy';
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(messageText);
      setStatus('Copied response', 'ok');
    } catch (_) {
      setStatus('Copy failed', 'error');
    }
  });

  const reuseBtn = document.createElement('button');
  reuseBtn.className = 'chip-btn';
  reuseBtn.type = 'button';
  reuseBtn.textContent = 'Use as prompt';
  reuseBtn.addEventListener('click', () => {
    el.prompt.value = messageText;
    updatePromptCount();
    el.prompt.focus();
    setStatus('Response moved to prompt box', 'ok');
  });

  actions.append(copyBtn, reuseBtn);
  return actions;
}

function renderMessages() {
  el.chat.innerHTML = '';

  if (!state.messages.length) {
    el.chat.appendChild(el.empty);
    updateChatMeta();
    return;
  }

  for (const message of state.messages) {
    const wrapper = document.createElement('div');
    wrapper.className = `msg ${message.role}`;

    const role = document.createElement('div');
    role.className = 'role';
    role.textContent = message.role;

    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (message.role === 'assistant') {
      bubble.innerHTML = renderMarkdown(message.content);
    } else {
      bubble.textContent = message.content;
    }

    wrapper.appendChild(role);
    wrapper.appendChild(bubble);

    if (message.role === 'assistant') {
      wrapper.appendChild(createAssistantActions(message.content));
    }

    el.chat.appendChild(wrapper);
  }

  updateChatMeta();
  el.chat.scrollTop = el.chat.scrollHeight;
}

function renderImageInfo() {
  if (!state.imageBase64) {
    el.attachmentBadge.classList.add('hidden');
    el.fileInfo.textContent = '';
    el.imagePreview.removeAttribute('src');
    return;
  }

  el.attachmentBadge.classList.remove('hidden');
  el.fileInfo.textContent = state.imageName || 'attached image';
  el.imagePreview.src = state.imagePreviewUrl || '';
}

function renderModels() {
  const current = el.model.value;
  el.model.innerHTML = '';

  if (!state.models.length) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No models found';
    el.model.appendChild(option);
    return;
  }

  for (const model of state.models) {
    const option = document.createElement('option');
    option.value = model;
    option.textContent = model;
    el.model.appendChild(option);
  }

  if (state.models.includes(current)) {
    el.model.value = current;
  } else {
    const preferred = state.models.find((name) => name.includes('qwen3-vl')) || state.models[0];
    el.model.value = preferred;
  }
}

async function loadModels() {
  setStatus('Loading models...', 'busy');
  try {
    const response = await fetch('/api/ollama/api/tags', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.models = (data.models || []).map((model) => model.name);
    renderModels();
    setStatus(`Ready • ${state.models.length} model${state.models.length === 1 ? '' : 's'}`, 'ok');
  } catch (error) {
    setStatus(`Could not load models: ${error.message}`, 'error');
  }
}

function loadImageElement(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => resolve({ img, dataUrl: String(reader.result || '') });
      img.onerror = reject;
      img.src = String(reader.result || '');
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function imageFileToOptimizedBase64(file) {
  const { img, dataUrl } = await loadImageElement(file);
  const maxSide = 1024;
  let width = img.width;
  let height = img.height;

  if (width > height && width > maxSide) {
    height = Math.round((height * maxSide) / width);
    width = maxSide;
  } else if (height >= width && height > maxSide) {
    width = Math.round((width * maxSide) / height);
    height = maxSide;
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0, width, height);

  const outDataUrl = canvas.toDataURL('image/jpeg', 0.82);
  const commaIndex = outDataUrl.indexOf(',');
  return {
    base64: commaIndex >= 0 ? outDataUrl.slice(commaIndex + 1) : outDataUrl,
    previewUrl: dataUrl,
    width,
    height,
    mime: 'image/jpeg'
  };
}

async function sendMessage(promptText) {
  if (state.busy) return;

  const model = el.model.value;
  if (!model) {
    setStatus('No model selected', 'error');
    return;
  }

  setBusy(true);
  setStatus(`Running ${model}...`, 'busy');

  state.messages.push({ role: 'user', content: promptText });
  renderMessages();

  const payloadMessages = state.messages.map((message) => ({
    role: message.role,
    content: message.content
  }));

  if (state.imageBase64) {
    payloadMessages[payloadMessages.length - 1].images = [state.imageBase64];
  }

  try {
    const response = await fetch('/api/ollama/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        stream: false,
        messages: payloadMessages,
        options: {
          temperature: Number(el.temperature.value || 0.7),
          num_predict: Number(el.numPredict.value || 512)
        }
      })
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }

    const data = await response.json();
    const answer = data?.message?.content || data?.response || data?.message?.thinking || '';

    if (!answer) {
      throw new Error('The model returned an empty response.');
    }

    state.messages.push({ role: 'assistant', content: answer });
    state.imageBase64 = null;
    state.imageMime = null;
    state.imageName = null;
    state.imagePreviewUrl = null;
    state.imageWidth = null;
    state.imageHeight = null;
    renderImageInfo();
    renderMessages();
    setStatus('Ready', 'ok');
  } catch (error) {
    state.messages.push({ role: 'system', content: `Error: ${error.message}` });
    renderMessages();
    setStatus('Request failed', 'error');
  } finally {
    setBusy(false);
  }
}

el.composer.addEventListener('submit', async (event) => {
  event.preventDefault();
  const promptText = el.prompt.value.trim();
  if (!promptText) return;
  el.prompt.value = '';
  updatePromptCount();
  await sendMessage(promptText);
});

el.prompt.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    el.composer.requestSubmit();
  }
});

el.prompt.addEventListener('input', updatePromptCount);

el.refreshBtn.addEventListener('click', loadModels);

el.clearBtn.addEventListener('click', () => {
  state.messages = [];
  renderMessages();
  setStatus('Chat cleared', 'ok');
});

el.imageInput.addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  try {
    const optimized = await imageFileToOptimizedBase64(file);
    state.imageBase64 = optimized.base64;
    state.imageMime = optimized.mime;
    state.imageName = file.name;
    state.imagePreviewUrl = optimized.previewUrl;
    state.imageWidth = optimized.width;
    state.imageHeight = optimized.height;
    renderImageInfo();
    setStatus(`Attached ${file.name}`, 'ok');
  } catch (error) {
    setStatus(`Could not read image: ${error.message}`, 'error');
  } finally {
    el.imageInput.value = '';
  }
});

el.removeImageBtn.addEventListener('click', () => {
  state.imageBase64 = null;
  state.imageMime = null;
  state.imageName = null;
  state.imagePreviewUrl = null;
  state.imageWidth = null;
  state.imageHeight = null;
  renderImageInfo();
  setStatus('Image removed', 'ok');
});

renderMessages();
renderImageInfo();
updatePromptCount();
setBusy(false);
loadModels();
