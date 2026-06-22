/* ═══════════════════════════════════════
   Reels Factory — app.js
   ═══════════════════════════════════════ */

let _imgModalIndex   = 0;
let _videoModalIndex = 0;
const _selected = new Set();   // 선택된 카드 인덱스

// ── 토스트 ──────────────────────────────
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (type ? ' ' + type : '');
  t.classList.remove('hidden');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.add('hidden'), 3200);
}

// ── 상태바 ──────────────────────────────
function setStatus(id, msg, type = 'info') {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = 'status-bar ' + type;
  el.classList.remove('hidden');
}

// ── 공통 폴링 ───────────────────────────
function pollJob(jobId, onProgress, onDone, onError) {
  const timer = setInterval(async () => {
    const p = await fetch(`/api/progress/${jobId}`).then(r => r.json());
    if (onProgress) onProgress(p);
    if (p.status === 'done')  { clearInterval(timer); if (onDone)  onDone(p); }
    if (p.status === 'error') { clearInterval(timer); if (onError) onError(p); }
  }, 1200);
}

// ════════════════════════════════════════
// STEP 1: 콘텐츠 기획
// ════════════════════════════════════════
async function generatePlan() {
  const btn      = document.getElementById('btn-gen-plan');
  const category = document.getElementById('category-select').value;
  const count    = parseInt(document.getElementById('count-select').value);

  btn.disabled    = true;
  btn.textContent = '⏳ GPT 기획 중...';
  setStatus('plan-status', `"${category}" 주제로 ${count}개 기획 중… (20~40초)`, 'loading');

  try {
    const res  = await fetch('/api/generate-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category, count }),
    });
    const data = await res.json();
    if (data.error) { setStatus('plan-status', '❌ ' + data.error, 'error'); return; }

    setStatus('plan-status', `✅ ${data.count}개 기획 완료! 이미지를 생성하세요.`, 'success');
    document.getElementById('stat-plan').textContent = data.count;
    renderPlanChips(data.plan);
    renderCardGrid(data.plan);
    showToast(`${data.count}개 기획 완료!`, 'success');
  } catch (e) {
    setStatus('plan-status', '❌ ' + e.message, 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = '✨ 콘텐츠 기획 생성';
  }
}

function renderPlanChips(plan) {
  const el = document.getElementById('plan-list');
  if (!plan?.length) { el.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div>기획안이 없습니다.</div>'; return; }
  el.innerHTML = `
    <div class="plan-summary-header">
      <span>총 ${plan.length}개 기획안</span>
      <button class="btn btn-green btn-sm" onclick="createAllImages()">🖼️ 전체 이미지 생성</button>
    </div>
    <div class="theme-chips">
      ${plan.map((item, i) => `
        <div class="theme-chip" id="chip-${i+1}" onclick="scrollToCard(${i+1})">
          <span class="chip-num">${i+1}</span>
          <span>${item.theme}</span>
        </div>`).join('')}
    </div>`;
}

// ════════════════════════════════════════
// STEP 2: 이미지 생성 & 그리드
// ════════════════════════════════════════
function renderCardGrid(plan) {
  document.getElementById('card-grid').innerHTML = plan.map((item, i) => `
    <div class="card-thumb" id="thumb-${i+1}" data-index="${i+1}">
      <label class="card-checkbox" onclick="event.stopPropagation()">
        <input type="checkbox" data-index="${i+1}"
               onchange="toggleCard(${i+1}, this.checked)">
        <span class="card-checkbox-mark"></span>
      </label>
      <div class="thumb-inner" onclick="openImageModal(${i+1}, '${escHtml(item.theme)}')">
        <div class="thumb-placeholder" onclick="event.stopPropagation(); createSingleImage(${i+1})">
          <span class="placeholder-icon">🖼️</span>
          <span class="placeholder-text">클릭하여 생성</span>
          <span class="placeholder-num">${i+1}</span>
        </div>
      </div>
      <div class="thumb-info">
        <div class="thumb-title">${i+1}. ${item.theme.slice(0,14)}</div>
        <div id="actions-${i+1}">${renderPendingActions(i+1)}</div>
      </div>
    </div>`).join('');
}

function renderPendingActions(index, hasCaption) {
  return `
    <div class="video-status pending"><span class="status-dot"></span>영상 미생성</div>
    <div class="caption-status ${hasCaption ? 'done' : 'pending'}">
      <span class="status-dot"></span>${hasCaption ? '캡션 저장 완료' : '캡션 미생성'}
    </div>
    <div class="thumb-actions" style="margin-top:8px">
      <button class="btn btn-outline btn-sm" style="width:100%" onclick="createSingleVideo(${index})">
        🎥 영상 생성
      </button>
      ${hasCaption ? `<button class="btn-caption-view" onclick="openCaptionModal(${index})">📝 캡션 보기</button>` : ''}
    </div>`;
}

function renderDoneActions(index, hasCaption) {
  return `
    <div class="video-status done"><span class="status-dot"></span>영상 저장 완료</div>
    <div class="thumb-actions" style="margin-top:8px">
      <button class="btn-preview" onclick="openVideoModal(${index}, '')">▶ 미리보기</button>
      <a href="/download/video/${index}" download class="btn-download">⬇ 다운로드</a>
    </div>
    ${hasCaption ? `
    <div style="display:flex;gap:6px;margin-top:6px">
      <button class="btn-caption-view" style="flex:1" onclick="toggleCaptionPreview(${index})">📝 캡션 보기</button>
      <button class="btn-caption-view" style="flex:1" onclick="openCaptionModal(${index})">✏️ 수정</button>
    </div>
    <div class="caption-preview-box hidden" id="caption-preview-${index}"></div>
    ` : `<div style="margin-top:6px"><button class="btn-caption-view" style="width:100%;opacity:.5" disabled>캡션 없음</button></div>`}`;
}

async function toggleCaptionPreview(index) {
  const box = document.getElementById(`caption-preview-${index}`);
  if (!box) return;
  if (!box.classList.contains('hidden')) {
    box.classList.add('hidden');
    return;
  }
  if (!box.textContent.trim()) {
    const d = await fetch(`/api/caption/${index}`).then(r => r.json());
    box.textContent = d.caption || '';
  }
  box.classList.remove('hidden');
}

function renderGeneratingActions() {
  return `
    <div class="video-status generating"><span class="status-dot"></span>영상 생성 중…</div>`;
}

// ── 캡션 모달 ────────────────────────────
async function openCaptionModal(index) {
  const data = await fetch(`/api/caption/${index}`).then(r => r.json());
  document.getElementById('caption-modal-index').textContent = index;
  document.getElementById('caption-textarea').value = data.caption || '';
  document.getElementById('caption-modal').classList.remove('hidden');
  document.getElementById('caption-save-btn').onclick = () => saveCaption(index);
}

function closeCaptionModal() {
  document.getElementById('caption-modal').classList.add('hidden');
}

async function saveCaption(index) {
  const caption = document.getElementById('caption-textarea').value;
  await fetch(`/api/caption/${index}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ caption }),
  });
  showToast(`${index}번 캡션 저장 완료!`, 'success');
  closeCaptionModal();
}

// ── 단일 이미지 생성 ────────────────────
async function createSingleImage(index) {
  setThumbLoading(index);
  const data = await fetch(`/api/create-image/${index}`, { method: 'POST' }).then(r => r.json());
  if (data.error) { setThumbError(index); showToast('이미지 생성 실패: ' + data.error, 'error'); return; }

  pollJob(data.job_id, null,
    () => { setThumbDone(index); showToast(`이미지 ${index}번 완료!`, 'success'); },
    (p) => { setThumbError(index); showToast('오류: ' + p.message, 'error'); }
  );
}

// ── 전체 이미지 생성 ────────────────────
async function createAllImages() {
  const wrap = document.getElementById('img-progress-wrap');
  wrap.classList.remove('hidden');
  setStatus('img-status', '전체 이미지 생성 시작…', 'loading');
  document.getElementById('section-images').scrollIntoView({ behavior: 'smooth' });

  const data = await fetch('/api/create-all-images', { method: 'POST' }).then(r => r.json());
  if (data.error) { setStatus('img-status', '❌ ' + data.error, 'error'); return; }

  const total = data.total;
  pollJob('img_all',
    (p) => {
      const done = p.done || 0;
      const pct  = Math.round((done / total) * 100);
      document.getElementById('img-progress-text').textContent = `${done} / ${total} 완료`;
      document.getElementById('img-progress-pct').textContent  = pct + '%';
      document.getElementById('img-progress-fill').style.width = pct + '%';
      setStatus('img-status', p.message, 'loading');
      if (done > 0) setThumbDone(done);
    },
    () => {
      setStatus('img-status', `✅ 전체 ${total}개 이미지 생성 완료! → output/images/`, 'success');
      showToast('모든 이미지 생성 완료!', 'success');
      for (let i = 1; i <= total; i++) setThumbDone(i);
      refreshStorageStatus();
    },
    (p) => setStatus('img-status', '❌ ' + p.message, 'error')
  );
}

// ── 썸네일 상태 업데이트 ────────────────
function setThumbLoading(index) {
  const inner = document.querySelector(`#thumb-${index} .thumb-inner`);
  if (!inner) return;
  inner.innerHTML = `
    <div class="thumb-placeholder">
      <span class="placeholder-icon" style="animation:spin 1s linear infinite;display:inline-block">⏳</span>
      <span class="placeholder-text">생성 중…</span>
    </div>`;
}

function setThumbDone(index) {
  const thumb = document.getElementById(`thumb-${index}`);
  if (!thumb) return;
  const inner = thumb.querySelector('.thumb-inner');
  const t = Date.now();
  inner.innerHTML = `
    <img src="/output/images/card_${index}.jpg?t=${t}" alt="카드 ${index}" loading="lazy">
    <div class="thumb-overlay"><span class="thumb-overlay-icon">🔍</span></div>`;
  inner.onclick = () => openImageModal(index, '');

  const chip = document.getElementById(`chip-${index}`);
  if (chip && !chip.classList.contains('has-img')) {
    chip.classList.add('has-img');
    chip.innerHTML += '<span class="chip-check">✓</span>';
  }
}

function setThumbError(index) {
  const inner = document.querySelector(`#thumb-${index} .thumb-inner`);
  if (!inner) return;
  inner.innerHTML = `
    <div class="thumb-placeholder" onclick="createSingleImage(${index})">
      <span class="placeholder-icon">⚠️</span>
      <span class="placeholder-text">실패 — 재시도</span>
    </div>`;
  inner.onclick = null;
}

// ── 이미지 모달 ─────────────────────────
function openImageModal(index, theme) {
  _imgModalIndex = index;
  const t = Date.now();
  document.getElementById('img-modal-src').src   = `/output/images/card_${index}.jpg?t=${t}`;
  document.getElementById('img-modal-title').textContent = `[${index}번] ${theme || '카드뉴스 미리보기'}`;
  document.getElementById('img-modal-overlay').classList.remove('hidden');
}
function closeImageModal() {
  document.getElementById('img-modal-overlay').classList.add('hidden');
}
function modalMakeVideo() {
  closeImageModal();
  createSingleVideo(_imgModalIndex);
  document.getElementById('section-video').scrollIntoView({ behavior: 'smooth' });
}

function scrollToCard(index) {
  document.getElementById('section-images').scrollIntoView({ behavior: 'smooth' });
  setTimeout(() => {
    const t = document.getElementById(`thumb-${index}`);
    if (t) t.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 420);
}

// ════════════════════════════════════════
// STEP 3: 영상 생성
// ════════════════════════════════════════
async function createSingleVideo(index) {
  // 액션 영역 → 생성 중 상태
  const actEl = document.getElementById(`actions-${index}`);
  if (actEl) actEl.innerHTML = renderGeneratingActions();

  setStatus('video-status', `[${index}번] 영상 생성 중…`, 'loading');
  document.getElementById('section-video').scrollIntoView({ behavior: 'smooth' });

  const data = await fetch('/api/create-video', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index }),
  }).then(r => r.json());

  if (data.error) {
    setStatus('video-status', '❌ ' + data.error, 'error');
    if (actEl) actEl.innerHTML = renderPendingActions(index);
    return;
  }

  pollJob(data.job_id, null,
    () => {
      setStatus('video-status', `✅ ${index}번 영상 생성 완료!`, 'success');
      showToast(`영상 ${index}번 완료!`, 'success');
      if (actEl) actEl.innerHTML = renderDoneActions(index);
      updateStatVideo();
    },
    (p) => {
      setStatus('video-status', '❌ ' + p.message, 'error');
      if (actEl) actEl.innerHTML = renderPendingActions(index);
    }
  );
}

async function createAllVideos() {
  const wrap = document.getElementById('video-progress-wrap');
  wrap.classList.remove('hidden');
  setStatus('video-status', '전체 영상 생성 시작…', 'loading');

  const data = await fetch('/api/create-all-videos', { method: 'POST' }).then(r => r.json());
  if (data.error) { setStatus('video-status', '❌ ' + data.error, 'error'); return; }

  const total = data.total;
  let lastDone = 0;

  pollJob('video_all',
    (p) => {
      const done = p.done || 0;
      const pct  = Math.round((done / total) * 100);
      document.getElementById('video-progress-text').textContent = `${done} / ${total} 완료`;
      document.getElementById('video-progress-pct').textContent  = pct + '%';
      document.getElementById('video-progress-fill').style.width = pct + '%';
      setStatus('video-status', p.message, 'loading');
      // 완성된 영상마다 버튼 업데이트
      if (done > lastDone) {
        for (let i = lastDone + 1; i <= done; i++) {
          const el = document.getElementById(`actions-${i}`);
          if (el) el.innerHTML = renderDoneActions(i);
        }
        lastDone = done;
      }
    },
    () => {
      setStatus('video-status', `✅ 전체 ${total}개 영상 생성 완료! → output/videos/`, 'success');
      showToast('모든 영상 생성 완료!', 'success');
      document.getElementById('stat-video').textContent = total;
      refreshStorageStatus();
    },
    (p) => setStatus('video-status', '❌ ' + p.message, 'error')
  );
}

function updateStatVideo() {
  const el = document.getElementById('stat-video');
  el.textContent = parseInt(el.textContent || '0') + 1;
}

// ════════════════════════════════════════
// DALL-E 3 배경 생성
// ════════════════════════════════════════
async function generateAllBgs() {
  const wrap = document.getElementById('bg-progress-wrap');
  wrap.classList.remove('hidden');
  setStatus('bg-status', 'DALL-E 3 배경 생성 시작… (카드 1개당 약 20초)', 'loading');

  const data = await fetch('/api/generate-all-bgs', { method: 'POST' }).then(r => r.json());
  if (data.error) { setStatus('bg-status', '❌ ' + data.error, 'error'); return; }

  const total = data.total;
  pollJob('bg_all',
    (p) => {
      const done = p.done || 0;
      const pct  = Math.round((done / total) * 100);
      document.getElementById('bg-progress-text').textContent = `${done} / ${total} 완료`;
      document.getElementById('bg-progress-pct').textContent  = pct + '%';
      document.getElementById('bg-progress-fill').style.width = pct + '%';
      setStatus('bg-status', p.message, 'loading');
      if (done > 0) setBgPreviewDone(done);
    },
    (p) => {
      const done   = p.done || 0;
      const errors = p.errors || [];
      if (done > 0) {
        setStatus('bg-status', `✅ ${done}/${total}개 배경 생성 완료!`, 'success');
        showToast(`🎨 배경 ${done}개 생성 완료!`, 'success');
      } else {
        const errMsg = (errors[0]) || p.message || 'DALL-E 이미지 생성 실패';
        setStatus('bg-status', '❌ ' + errMsg, 'error');
        showToast('❌ 배경 생성 실패 — 콘솔 확인', 'error');
      }
    },
    (p) => setStatus('bg-status', '❌ ' + p.message, 'error')
  );
}

async function regenSingleBg(index) {
  const item = document.getElementById(`bgprev-${index}`);
  if (item) {
    const thumb = item.querySelector('.bg-preview-thumb');
    thumb.innerHTML = '<div class="bg-placeholder spinning"><span>⏳</span></div>';
  }
  const data = await fetch(`/api/generate-bg/${index}`, { method: 'POST' }).then(r => r.json());
  if (data.error) { showToast('❌ ' + data.error, 'error'); return; }

  pollJob(data.job_id, null,
    () => { setBgPreviewDone(index); showToast(`🎨 ${index}번 배경 재생성 완료!`, 'success'); },
    (p) => { showToast('❌ ' + p.message, 'error'); }
  );
}

function setBgPreviewDone(index) {
  const item = document.getElementById(`bgprev-${index}`);
  if (!item) return;
  const thumb = item.querySelector('.bg-preview-thumb');
  const t = Date.now();
  thumb.innerHTML = `
    <img src="/assets/bg_card_${index}.jpg?t=${t}" alt="배경 ${index}" loading="lazy">
    <div class="bg-check">✓</div>`;
}

// ════════════════════════════════════════
// 선택 & ZIP 다운로드
// ════════════════════════════════════════
function toggleCard(index, checked) {
  checked ? _selected.add(index) : _selected.delete(index);
  _updateSelectionUI();
}

function toggleSelectAll(checked) {
  document.querySelectorAll('.card-thumb input[type=checkbox]').forEach(cb => {
    const idx = parseInt(cb.dataset.index);
    cb.checked = checked;
    checked ? _selected.add(idx) : _selected.delete(idx);
  });
  _updateSelectionUI();
}

function _updateSelectionUI() {
  const count  = _selected.size;
  const badge  = document.getElementById('selected-badge');
  const btnDl  = document.getElementById('btn-dl-selected');
  const chkAll = document.getElementById('chk-all');

  badge.textContent = `${count}개 선택됨`;
  badge.classList.toggle('hidden', count === 0);
  btnDl.disabled = count === 0;

  const total = document.querySelectorAll('.card-thumb input[type=checkbox]').length;
  if (chkAll) chkAll.indeterminate = count > 0 && count < total;
  if (chkAll) chkAll.checked = count === total && total > 0;
}

async function downloadSelectedZip() {
  if (_selected.size === 0) { showToast('선택된 카드가 없습니다.', 'error'); return; }
  await _triggerZip('selected', [..._selected].sort((a,b) => a-b));
}

async function downloadAllZip() {
  await _triggerZip('all', []);
}

async function _triggerZip(type, indices) {
  showToast('ZIP 파일 준비 중…');
  try {
    const res = await fetch('/api/download/zip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, indices }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast('❌ ' + (err.error || '다운로드 실패'), 'error');
      return;
    }
    // 브라우저 파일 다운로드 트리거
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const date = new Date().toISOString().slice(0,10).replace(/-/g,'');
    a.href     = url;
    a.download = `silver_contents_${date}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ ZIP 다운로드 시작!', 'success');
  } catch (e) {
    showToast('❌ ' + e.message, 'error');
  }
}

// 저장 현황 업데이트
async function refreshStorageStatus() {
  try {
    const s = await fetch('/api/storage-status').then(r => r.json());
    const imgEl = document.getElementById('stat-img-count');
    const vidEl = document.getElementById('stat-vid-count');
    const capEl = document.getElementById('stat-cap-count');
    if (imgEl) imgEl.textContent = s.images;
    if (vidEl) vidEl.textContent = s.videos;
    if (capEl) capEl.textContent = s.captions;
  } catch (_) {}
}

// ── 영상 미리보기 모달 ──────────────────
function openVideoModal(index, theme) {
  _videoModalIndex = index;
  const t   = Date.now();
  const src = `/output/videos/output_${index}.mp4?t=${t}`;
  document.getElementById('modal-video-src').src = src;
  document.getElementById('modal-video').load();
  document.getElementById('video-modal-title').textContent = theme ? `[${index}번] ${theme}` : `영상 미리보기 #${index}`;
  document.getElementById('modal-download-btn').setAttribute('data-index', index);
  document.getElementById('video-modal-overlay').classList.remove('hidden');
}
function closeVideoModal() {
  const v = document.getElementById('modal-video');
  v.pause();
  v.src = '';
  document.getElementById('modal-video-src').src = '';
  document.getElementById('video-modal-overlay').classList.add('hidden');
}
function downloadFromModal() {
  const index = _videoModalIndex;
  const a = document.createElement('a');
  a.href = `/download/video/${index}`;
  a.download = `output_${index}.mp4`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ════════════════════════════════════════
// STEP 4: Buffer 멀티플랫폼 예약
// ════════════════════════════════════════

// ── 플랫폼 전체 선택/해제 ──────────────
function setAllPlatforms(value) {
  ['plat-instagram','plat-tiktok','plat-youtube'].forEach(id => {
    document.getElementById(id).checked = value;
  });
}

// ── 예약 시간 모드 전환 ────────────────
function onSchedModeChange() {
  const mode = document.querySelector('input[name="sched-mode"]:checked').value;
  document.getElementById('custom-times-wrap').classList.toggle('hidden', mode !== 'custom');
}

// ── 채널 변경 시 미리보기 갱신 ─────────
let _channelsCache = null;
async function _loadChannels() {
  if (!_channelsCache) {
    _channelsCache = await fetch('/api/channels').then(r => r.json());
  }
  return _channelsCache;
}

async function onChannelChange() {
  const channelId = document.getElementById('buffer-channel-select').value;
  const data      = await _loadChannels();
  const ch        = data.channels.find(c => c.id === channelId);
  const preview   = document.getElementById('channel-preview');
  if (!ch) { preview.innerHTML = ''; return; }
  const p = ch.platforms;
  preview.innerHTML = `
    <div class="channel-preview-item"><span class="cp-icon">📷</span><span class="cp-handle">${p.instagram?.handle || '미설정'}</span></div>
    <div class="channel-preview-item"><span class="cp-icon">🎵</span><span class="cp-handle">${p.tiktok?.handle || '미설정'}</span></div>
    <div class="channel-preview-item"><span class="cp-icon">▶️</span><span class="cp-handle">${p.youtube?.handle || '미설정'}</span></div>
  `;
}

// ── 채널 설정 모달 ─────────────────────
async function openChannelSettings() {
  const data = await _loadChannels();
  const list = document.getElementById('channel-settings-list');
  list.innerHTML = data.channels.map(ch => `
    <div class="ch-setting-block" data-id="${ch.id}">
      <div class="ch-setting-name">${ch.name}</div>
      <div class="ch-setting-grid">
        ${['instagram','tiktok','youtube'].map(plat => {
          const pid   = ch.platforms?.[plat]?.profile_id || '';
          const hnd   = ch.platforms?.[plat]?.handle || '';
          const icons = {instagram:'📷',tiktok:'🎵',youtube:'▶️'};
          return `
            <div class="ch-plat-row">
              <span class="ch-plat-label">${icons[plat]} ${plat}</span>
              <input class="ch-pid-input" data-plat="${plat}" placeholder="profile_id"
                     value="${pid}" style="flex:1;min-width:0">
              <input class="ch-handle-input" data-plat="${plat}" placeholder="@handle"
                     value="${hnd}" style="width:120px">
            </div>`;
        }).join('')}
      </div>
    </div>
  `).join('<hr style="margin:16px 0;border:none;border-top:1px solid #e2e8f0">');
  document.getElementById('channel-settings-modal').classList.remove('hidden');
}

function closeChannelSettings() {
  document.getElementById('channel-settings-modal').classList.add('hidden');
}

async function saveChannelSettings() {
  const data   = await _loadChannels();
  const blocks = document.querySelectorAll('.ch-setting-block');
  blocks.forEach(block => {
    const id = block.dataset.id;
    const ch = data.channels.find(c => c.id === id);
    if (!ch) return;
    ['instagram','tiktok','youtube'].forEach(plat => {
      const pidEl  = block.querySelector(`.ch-pid-input[data-plat="${plat}"]`);
      const hndEl  = block.querySelector(`.ch-handle-input[data-plat="${plat}"]`);
      if (!ch.platforms[plat]) ch.platforms[plat] = {};
      if (pidEl) ch.platforms[plat].profile_id = pidEl.value.trim();
      if (hndEl) ch.platforms[plat].handle     = hndEl.value.trim();
    });
  });
  await fetch('/api/channels', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  _channelsCache = null; // 캐시 무효화
  closeChannelSettings();
  onChannelChange();     // 미리보기 갱신
  showToast('채널 설정 저장 완료!', 'success');
}

// ── Buffer 예약 발행 ───────────────────
async function scheduleBuffer() {
  const platforms = [];
  if (document.getElementById('plat-instagram').checked) platforms.push('instagram');
  if (document.getElementById('plat-tiktok').checked)    platforms.push('tiktok');
  if (document.getElementById('plat-youtube').checked)   platforms.push('youtube');
  if (!platforms.length) { showToast('플랫폼을 하나 이상 선택하세요.', 'error'); return; }

  const channelId = document.getElementById('buffer-channel-select').value;
  const mode      = document.querySelector('input[name="sched-mode"]:checked').value;
  const timesKst  = mode === 'custom'
    ? document.getElementById('custom-times-input').value.split(',').map(t => t.trim()).filter(Boolean)
    : ['09:00','14:00','19:00'];

  document.getElementById('buffer-progress-wrap').classList.remove('hidden');
  setStatus('buffer-status', 'Buffer 예약 시작…', 'loading');

  // 플랫폼별 카운터 초기화
  const statEls = { instagram: 'bpp-ig-stat', tiktok: 'bpp-tt-stat', youtube: 'bpp-yt-stat' };

  const data = await fetch('/api/schedule-buffer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ platforms, channel_id: channelId, times_kst: timesKst }),
  }).then(r => r.json());
  if (data.error) { setStatus('buffer-status', '❌ ' + data.error, 'error'); return; }

  const total = data.total || 0;
  pollJob('buffer_all',
    (p) => {
      const done = p.done || 0;
      const pct  = Math.round((done / total) * 100);
      document.getElementById('buffer-progress-fill').style.width = pct + '%';
      document.getElementById('buffer-progress-pct').textContent  = pct + '%';
      document.getElementById('buffer-progress-text').textContent = p.message || '';
      // 플랫폼별 카운터
      const pmap = p.platforms || {};
      platforms.forEach(plat => {
        const el = document.getElementById(statEls[plat]);
        if (el && pmap[plat]) {
          el.textContent = `${pmap[plat].done} / ${total} ✓  ${pmap[plat].error ? '⚠' + pmap[plat].error : ''}`;
        }
      });
      setStatus('buffer-status', p.message, 'loading');
    },
    () => {
      setStatus('buffer-status', `✅ 전체 ${total}개 예약 완료!`, 'success');
      showToast('Buffer 멀티플랫폼 예약 완료!', 'success');
      refreshHistory();
    },
    (p) => setStatus('buffer-status', '❌ ' + p.message, 'error')
  );
}

// ── 이력 ────────────────────────────────
async function refreshHistory() {
  const h = await fetch('/api/history').then(r => r.json());
  const el = document.getElementById('history-list');
  if (!h.length) {
    el.innerHTML = '<div class="empty-state"><div class="empty-icon">🕐</div>이력이 없습니다.</div>';
    return;
  }
  el.innerHTML = h.map(item => `
    <div class="history-item">
      <span class="history-type">${item.type}</span>
      <span class="history-detail">${item.theme || item.category || ''}${item.count ? ' — ' + item.count + '개' : ''}</span>
      <span class="history-time">${item.timestamp}</span>
    </div>`).join('');
}

// ── 유틸 ────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// 스핀 애니메이션
const _s = document.createElement('style');
_s.textContent = '@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}';
document.head.appendChild(_s);

// ESC 키로 모달 닫기
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeImageModal(); closeVideoModal(); }
});
