/* ═══════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════ */
function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ═══════════════════════════════════════════════
   FLATPICKR — date / time pickers
   ═══════════════════════════════════════════════ */
const fpDate = flatpickr('#meeting_date', {
  locale: 'ru',
  dateFormat: 'Y-m-d',
  disableMobile: true,
  allowInput: false,
});

const fpEnd = flatpickr('#end_time', {
  enableTime: true,
  noCalendar: true,
  time_24hr: true,
  dateFormat: 'H:i',
  minuteIncrement: 5,
  disableMobile: true,
  allowInput: false,
});

const fpStart = flatpickr('#start_time', {
  enableTime: true,
  noCalendar: true,
  time_24hr: true,
  dateFormat: 'H:i',
  minuteIncrement: 5,
  disableMobile: true,
  allowInput: false,
  onClose(selected) {
    if (!selected.length) return;
    const endVal = fpEnd.selectedDates[0];
    if (!endVal || endVal <= selected[0]) {
      fpEnd.setDate(new Date(selected[0].getTime() + 60 * 60 * 1000));
    }
  },
});

/* ═══════════════════════════════════════════════
   ADD / EDIT MEETING MODAL
   ═══════════════════════════════════════════════ */
const addOverlay = document.getElementById('modalOverlay');
const openBtn    = document.getElementById('openModal');
const closeBtn   = document.getElementById('closeModal');
const cancelBtn  = document.getElementById('cancelModal');
const form       = document.getElementById('meetingForm');
const submitBtn  = document.getElementById('submitBtn');
const alertBox   = document.getElementById('conflictAlert');
const alertText  = document.getElementById('conflictText');

function showConflict(msg) {
  alertText.textContent = msg;
  alertBox.classList.add('is-visible');
}

function hideConflict() {
  alertBox.classList.remove('is-visible');
  alertText.textContent = '';
}

function openAddModal() {
  addOverlay.classList.add('is-open');
  prefillForm();
  document.getElementById('organizer').focus();
}

function closeAddModal() {
  addOverlay.classList.remove('is-open');
  hideConflict();
  form.reset();
  fpDate.clear();
  fpStart.clear();
  fpEnd.clear();
  delete form.dataset.editId;
  document.getElementById('modalTitle').textContent = 'Новая встреча';
  submitBtn.textContent = 'Добавить';
}

function prefillForm() {
  const orgEl = document.getElementById('organizer');
  if (!orgEl.value && window.CURRENT_USER) orgEl.value = window.CURRENT_USER;

  if (fpDate.selectedDates.length) return;

  const now = new Date();
  now.setSeconds(0, 0);
  now.setMinutes(Math.ceil(now.getMinutes() / 5) * 5);

  fpDate.setDate(now);
  fpStart.setDate(now);
  fpEnd.setDate(new Date(now.getTime() + 60 * 60 * 1000));
}

openBtn.addEventListener('click', openAddModal);
closeBtn.addEventListener('click', closeAddModal);
cancelBtn.addEventListener('click', closeAddModal);
addOverlay.addEventListener('click', (e) => { if (e.target === addOverlay) closeAddModal(); });

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideConflict();

  const organizer = form.organizer.value.trim();
  const with_whom = form.with_whom.value.split('\n').map(s => s.trim()).filter(Boolean);
  const dateVal   = form.meeting_date.value;
  const startTime = form.start_time.value;
  const endTime   = form.end_time.value;
  const start     = dateVal && startTime ? `${dateVal}T${startTime}:00` : '';
  const end       = dateVal && endTime   ? `${dateVal}T${endTime}:00`   : '';
  const comment   = form.comment.value.trim() || null;

  if (!organizer)              { showConflict('Укажите ваше имя.'); return; }
  if (!with_whom.length)       { showConflict('Укажите хотя бы одного участника.'); return; }
  if (!dateVal)                { showConflict('Укажите дату встречи.'); return; }
  if (!startTime || !endTime)  { showConflict('Укажите время начала и конца.'); return; }
  if (start >= end)            { showConflict('Время конца должно быть позже начала.'); return; }

  const editId = form.dataset.editId || null;
  const url    = editId ? `/api/meetings/${editId}` : '/api/meetings';
  const method = editId ? 'PUT' : 'POST';
  const okCode = editId ? 200 : 201;

  submitBtn.disabled = true;
  submitBtn.textContent = 'Сохраняю…';

  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ organizer, with_whom, start, end, comment }),
    });

    if (res.status === okCode) {
      closeAddModal();
      window.location.reload();
    } else if (res.status === 409) {
      const data = await res.json();
      showConflict(data.detail?.message || 'Конфликт расписания.');
    } else {
      const data = await res.json().catch(() => ({}));
      showConflict(data.detail || 'Ошибка при сохранении.');
    }
  } catch {
    showConflict('Ошибка сети. Попробуйте ещё раз.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = editId ? 'Сохранить' : 'Добавить';
  }
});

/* ═══════════════════════════════════════════════
   MEETING DETAIL MODAL
   ═══════════════════════════════════════════════ */
const detailOverlay     = document.getElementById('detailOverlay');
const closeDetailBtn    = document.getElementById('closeDetail');
const detailTimeBadge   = document.getElementById('detailTimeBadge');
const detailDate        = document.getElementById('detailDate');
const detailOrganizer   = document.getElementById('detailOrganizer');
const detailWith        = document.getElementById('detailWith');
const detailWithSection = document.getElementById('detailWithSection');
const detailComment     = document.getElementById('detailComment');
const detailCommentSect = document.getElementById('detailCommentSection');
const editMeetingBtn    = document.getElementById('editMeetingBtn');
const deleteMeetingBtn  = document.getElementById('deleteMeetingBtn');
const detailConflict    = document.getElementById('detailConflictAlert');
const detailConflictText = document.getElementById('detailConflictText');

let activeMeeting = null;

function openDetailModal(meeting) {
  activeMeeting = meeting;
  detailTimeBadge.textContent = `${meeting.start} – ${meeting.end}`;
  detailDate.textContent      = meeting.date;
  detailOrganizer.textContent = meeting.organizer;

  detailWith.innerHTML = '';
  if (meeting.with_whom?.length) {
    meeting.with_whom.forEach(name => {
      const pill = document.createElement('span');
      pill.className = 'pill';
      pill.innerHTML = `<span class="dot dot--blue"></span>${escapeHtml(name)}`;
      detailWith.appendChild(pill);
    });
    detailWithSection.style.display = '';
  } else {
    detailWithSection.style.display = 'none';
  }

  if (meeting.comment) {
    detailComment.textContent = meeting.comment;
    detailCommentSect.style.display = '';
  } else {
    detailCommentSect.style.display = 'none';
  }

  detailConflict.classList.remove('is-visible');

  const isOwn = window.CURRENT_USER && meeting.organizer === window.CURRENT_USER;
  editMeetingBtn.style.display   = isOwn ? '' : 'none';
  deleteMeetingBtn.style.display = isOwn ? '' : 'none';

  detailOverlay.classList.add('is-open');
}

function closeDetailModal() {
  detailOverlay.classList.remove('is-open');
  activeMeeting = null;
}

closeDetailBtn.addEventListener('click', closeDetailModal);
detailOverlay.addEventListener('click', (e) => { if (e.target === detailOverlay) closeDetailModal(); });

function triggerEdit(m) {
  document.getElementById('organizer').value = m.organizer;
  document.getElementById('with_whom').value = m.with_whom.join('\n');
  document.getElementById('comment').value   = m.comment || '';

  const [day, month, year] = m.date.split('.');
  fpDate.setDate(`${year}-${month}-${day}`);
  fpStart.setDate(m.start, false, 'H:i');
  fpEnd.setDate(m.end, false, 'H:i');

  form.dataset.editId = m.id;
  document.getElementById('modalTitle').textContent = 'Редактировать встречу';
  submitBtn.textContent = 'Сохранить';
  addOverlay.classList.add('is-open');
}

editMeetingBtn.addEventListener('click', () => {
  if (!activeMeeting) return;
  const m = activeMeeting;
  closeDetailModal();
  triggerEdit(m);
});

deleteMeetingBtn.addEventListener('click', () => {
  if (!activeMeeting) return;
  openConfirmModal(activeMeeting);
});

/* ═══════════════════════════════════════════════
   CONFIRM DELETE MODAL
   ═══════════════════════════════════════════════ */
const confirmOverlay   = document.getElementById('confirmOverlay');
const confirmCancelBtn = document.getElementById('confirmCancel');
const confirmOkBtn     = document.getElementById('confirmOk');
const confirmBodyText  = document.getElementById('confirmBodyText');

let pendingDeleteMeeting = null;

function openConfirmModal(meeting) {
  pendingDeleteMeeting = meeting;
  confirmBodyText.textContent =
    `${meeting.organizer} — ${meeting.date}, ${meeting.start}–${meeting.end}`;
  confirmOverlay.classList.add('is-open');
}

function closeConfirmModal() {
  confirmOverlay.classList.remove('is-open');
  pendingDeleteMeeting = null;
}

confirmCancelBtn.addEventListener('click', closeConfirmModal);
confirmOverlay.addEventListener('click', (e) => { if (e.target === confirmOverlay) closeConfirmModal(); });

confirmOkBtn.addEventListener('click', async () => {
  if (!pendingDeleteMeeting) return;
  const meeting = pendingDeleteMeeting;

  confirmOkBtn.disabled = true;
  confirmOkBtn.textContent = 'Удаляю…';

  try {
    const res = await fetch(`/api/meetings/${meeting.id}`, { method: 'DELETE' });
    if (res.status === 204) {
      closeConfirmModal();
      closeDetailModal();
      window.location.reload();
    } else {
      const data = await res.json().catch(() => ({}));
      closeConfirmModal();
      detailConflictText.textContent = data.detail || 'Не удалось удалить встречу.';
      detailConflict.classList.add('is-visible');
      detailOverlay.classList.add('is-open');
    }
  } catch {
    closeConfirmModal();
    detailConflictText.textContent = 'Ошибка сети.';
    detailConflict.classList.add('is-visible');
    detailOverlay.classList.add('is-open');
  } finally {
    confirmOkBtn.disabled = false;
    confirmOkBtn.textContent = 'Удалить';
  }
});

/* ═══════════════════════════════════════════════
   GLOBAL EVENT HANDLERS
   ═══════════════════════════════════════════════ */
document.addEventListener('click', (e) => {
  // Today-card action buttons
  const editBtn   = e.target.closest('.today-card__btn--edit');
  const deleteBtn = e.target.closest('.today-card__btn--delete');
  if (editBtn || deleteBtn) {
    e.stopPropagation();
    const card = (editBtn || deleteBtn).closest('.today-card');
    try {
      const meeting = JSON.parse(card.dataset.meeting);
      if (editBtn)   { triggerEdit(meeting); }
      if (deleteBtn) { openConfirmModal(meeting); }
    } catch (err) { console.error(err); }
    return;
  }

  // Card click → detail modal
  const card = e.target.closest('.meeting-card, .today-card');
  if (!card) return;
  try {
    openDetailModal(JSON.parse(card.dataset.meeting));
  } catch (err) {
    console.error('Failed to parse meeting data', err);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (confirmOverlay.classList.contains('is-open')) { closeConfirmModal(); return; }
    if (detailOverlay.classList.contains('is-open'))  { closeDetailModal(); return; }
    if (addOverlay.classList.contains('is-open'))     { closeAddModal(); return; }
  }
  if ((e.key === 'Enter' || e.key === ' ') &&
      (e.target.classList.contains('meeting-card') || e.target.classList.contains('today-card'))) {
    e.preventDefault();
    try { openDetailModal(JSON.parse(e.target.dataset.meeting)); } catch {}
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const body = document.getElementById('calendarBody');
  if (body) body.scrollTop = 8 * 60;

  // Hide edit/delete buttons on cards belonging to other users
  document.querySelectorAll('.today-card').forEach(card => {
    if (card.dataset.organizer !== window.CURRENT_USER) {
      card.querySelectorAll('.today-card__btn').forEach(btn => {
        btn.style.display = 'none';
      });
    }
  });
});
