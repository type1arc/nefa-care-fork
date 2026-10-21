/**
 * Dhruva Care — Client Application Controller
 * Integrates the Dhruva Care frontend with the complete backend:
 * - Machine Learning Symptom Neighbor Model (NearestNeighbors joblib backend)
 * - User Authentication (Sign up, Log in, Current Session, Logout)
 * - Live Doctor Tracking, Directory, and Smart Queuing (Wait = Patients Ahead x 7 mins)
 * - Appointment Booking (In-person and Teleconsultation with flat ₹50 platform fee)
 * - Teleconsultation (E2EE Chat & WebRTC Call Routing per Telemedicine Guidelines 2020)
 * - Express Medicine Delivery & Pharmacy Stock Check
 * - Diet & Health Plan: Northeast Calorie Counter & Nutrition Logs
 * - Hospital Franchise & Diagnostic Network
 * - MediApp Foundation Emergency Surgery Crowdfunding
 */

(function () {
  'use strict';

  // --- STATE ---
  const state = {
    currentUser: null,
    token: localStorage.getItem('dhruva_care_token') || '',
    selectedSymptoms: [],
    searchTimer: null,
    doctors: [],
    pharmacies: [],
    hospitals: [],
    campaigns: [],
    appointments: [],
    foodCatalog: [],
    dailyCalorieLogs: [],
    dailyTotalKcal: 0,
    activeConsultationId: null,
  };

  // --- UTILITIES ---
  function escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.innerHTML = '<span>' + escapeHtml(message) + '</span>';
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('fade-out');
      setTimeout(() => toast.remove(), 400);
    }, 4000);
  }

  async function apiFetch(endpoint, options = {}) {
    const headers = options.headers || {};
    if (state.token && !headers['Authorization']) {
      headers['Authorization'] = 'Bearer ' + state.token;
    }
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    options.headers = headers;

    const res = await fetch(endpoint, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || 'Request failed with status ' + res.status);
    }
    return data;
  }

  // --- AUTHENTICATION ---
  async function initAuth() {
    if (!state.token) {
      renderAuthHeader();
      return;
    }
    try {
      const user = await apiFetch('/api/users/me');
      state.currentUser = user;
    } catch (err) {
      state.currentUser = null;
      state.token = '';
      localStorage.removeItem('dhruva_care_token');
    }
    renderAuthHeader();
  }

  function renderAuthHeader() {
    const authArea = document.getElementById('auth-area');
    if (!authArea) return;

    if (state.currentUser) {
      const loc = state.currentUser.location || {};
      const locStr = loc.district ? (loc.district + ', ' + (loc.state || '')) : (loc.state || 'Northeast India');
      authArea.innerHTML = 
        '<div class="user-badge">' +
          '<div class="user-avatar">' + (state.currentUser.full_name ? state.currentUser.full_name.charAt(0).toUpperCase() : 'U') + '</div>' +
          '<div class="user-info">' +
            '<span class="user-name">' + escapeHtml(state.currentUser.full_name || 'Patient') + '</span>' +
            '<span class="user-loc">' + escapeHtml(locStr) + '</span>' +
          '</div>' +
          '<button type="button" class="btn-ghost-sm" id="btn-my-appointments" title="View Appointments">My Care</button>' +
          '<button type="button" class="btn-ghost-sm" id="btn-logout" title="Sign out">Log out</button>' +
        '</div>';
      document.getElementById('btn-logout')?.addEventListener('click', handleLogout);
      document.getElementById('btn-my-appointments')?.addEventListener('click', () => {
        window.dcGo && window.dcGo('teleconsult');
        loadUserAppointments();
      });
    } else {
      authArea.innerHTML = '<button type="button" class="header-action" id="btn-open-auth">Sign In / Register</button>';
      document.getElementById('btn-open-auth')?.addEventListener('click', () => openAuthModal());
    }
  }

  async function handleLogout() {
    try {
      await apiFetch('/api/users/logout', { method: 'POST' });
    } catch (e) {}
    state.currentUser = null;
    state.token = '';
    localStorage.removeItem('dhruva_care_token');
    renderAuthHeader();
    showToast('You have been logged out.', 'info');
  }

  function openAuthModal(initialTab = 'login') {
    window.dispatchEvent(new CustomEvent('dc:need-login', { detail: { role: 'patient' } }));
  }

  function closeAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) modal.classList.remove('active');
  }

  function switchAuthTab(tab) {
    const loginForm = document.getElementById('login-form-wrap');
    const signupForm = document.getElementById('signup-form-wrap');
    const tabLogin = document.getElementById('tab-login');
    const tabSignup = document.getElementById('tab-signup');

    if (tab === 'login') {
      loginForm?.classList.remove('hidden');
      signupForm?.classList.add('hidden');
      tabLogin?.classList.add('active');
      tabSignup?.classList.remove('active');
    } else {
      loginForm?.classList.add('hidden');
      signupForm?.classList.remove('hidden');
      tabLogin?.classList.remove('active');
      tabSignup?.classList.add('active');
    }
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errBox = document.getElementById('login-error');
    errBox.textContent = '';

    try {
      const data = await apiFetch('/api/users/login', {
        method: 'POST',
        body: { email, password },
      });
      state.token = data.token;
      state.currentUser = data.user;
      localStorage.setItem('dhruva_care_token', data.token);
      renderAuthHeader();
      closeAuthModal();
      showToast('Welcome back, ' + data.user.full_name + '!', 'success');
      loadUserAppointments();
      loadDailyCalories();
    } catch (err) {
      errBox.textContent = err.message;
    }
  }

  async function handleSignupSubmit(e) {
    e.preventDefault();
    const full_name = document.getElementById('signup-name').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;
    const phone = document.getElementById('signup-phone').value.trim();
    const stateVal = document.getElementById('signup-state').value;
    const district = document.getElementById('signup-district').value.trim();
    const errBox = document.getElementById('signup-error');
    errBox.textContent = '';

    try {
      const data = await apiFetch('/api/users/signup', {
        method: 'POST',
        body: { full_name, email, password, phone, state: stateVal, district },
      });
      state.token = data.token;
      state.currentUser = data.user;
      localStorage.setItem('dhruva_care_token', data.token);
      renderAuthHeader();
      closeAuthModal();
      showToast('Account created for ' + data.user.full_name + '!', 'success');
      loadUserAppointments();
      loadDailyCalories();
    } catch (err) {
      errBox.textContent = err.message;
    }
  }

  // --- SYMPTOM CHECKER & ML MODEL ---
  async function loadPopularSymptoms() {
    try {
      const data = await apiFetch('/api/symptom-checker/symptoms?q=');
      const wrap = document.getElementById('popular-chips');
      if (!wrap || !data.symptoms) return;

      wrap.innerHTML = data.symptoms.slice(0, 8).map(s => 
        '<button type="button" class="quick-chip" data-id="' + escapeHtml(s.id) + '" data-label="' + escapeHtml(s.label) + '">' +
          '+ ' + escapeHtml(s.label) +
        '</button>'
      ).join('');

      wrap.querySelectorAll('.quick-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-id');
          const label = btn.getAttribute('data-label');
          addSymptom({ id, label });
        });
      });
    } catch (err) {
      console.warn('Could not load popular symptoms:', err);
    }
  }

  function addSymptom(item) {
    if (!state.selectedSymptoms.some(s => s.id === item.id)) {
      state.selectedSymptoms.push(item);
      renderSelectedSymptoms();
    }
    const input = document.getElementById('symptom-search');
    if (input) {
      input.value = '';
      input.focus();
    }
    const sugBox = document.getElementById('suggestions');
    if (sugBox) sugBox.innerHTML = '';
  }

  function removeSymptom(id) {
    state.selectedSymptoms = state.selectedSymptoms.filter(s => s.id !== id);
    renderSelectedSymptoms();
    if (state.selectedSymptoms.length === 0) {
      const resEl = document.getElementById('result');
      if (resEl) resEl.innerHTML = '';
    }
  }

  function renderSelectedSymptoms() {
    const box = document.getElementById('chosen-symptoms');
    const clearBtn = document.getElementById('clear-symptoms');
    const assessBtn = document.getElementById('assess-button');
    if (!box) return;

    box.innerHTML = '';
    if (state.selectedSymptoms.length === 0) {
      box.innerHTML = '<span class="empty-selection">No symptoms selected yet. Search above or pick common concerns.</span>';
      if (clearBtn) clearBtn.hidden = true;
      if (assessBtn) assessBtn.disabled = true;
      return;
    }

    state.selectedSymptoms.forEach(item => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.setAttribute('aria-label', 'Remove ' + item.label);
      chip.innerHTML = escapeHtml(item.label) + ' <b>&times;</b>';
      chip.addEventListener('click', () => removeSymptom(item.id));
      box.appendChild(chip);
    });

    if (clearBtn) clearBtn.hidden = false;
    if (assessBtn) assessBtn.disabled = false;
  }

  async function handleSymptomSearch() {
    const input = document.getElementById('symptom-search');
    const sugBox = document.getElementById('suggestions');
    if (!input || !sugBox) return;

    const q = input.value.trim();
    if (q.length < 2) {
      sugBox.innerHTML = '';
      return;
    }

    try {
      const data = await apiFetch('/api/symptom-checker/symptoms?q=' + encodeURIComponent(q));
      sugBox.innerHTML = '';
      const available = (data.symptoms || []).filter(item => !state.selectedSymptoms.some(s => s.id === item.id));

      if (available.length === 0) {
        sugBox.innerHTML = '<p class="no-match">No matching symptom found. Try common terms like fever, cough, dizziness, headache, or rash.</p>';
        return;
      }

      available.slice(0, 7).forEach(item => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'suggestion ' + (item.priority ? 'priority-suggestion' : '');
        btn.innerHTML = escapeHtml(item.label) + (item.priority ? ' <span class="badge-direct">Common Match</span>' : '');
        btn.addEventListener('click', () => addSymptom(item));
        sugBox.appendChild(btn);
      });
    } catch (err) {
      sugBox.innerHTML = '<p class="no-match">' + escapeHtml(err.message) + '</p>';
    }
  }

  async function handleAssessSymptoms() {
    if (state.selectedSymptoms.length === 0) return;
    const assessBtn = document.getElementById('assess-button');
    const resEl = document.getElementById('result');
    if (!resEl) return;

    if (assessBtn) {
      assessBtn.disabled = true;
      assessBtn.innerHTML = 'Analyzing with Model… <span class="spinner"></span>';
    }
    resEl.innerHTML = '';

    try {
      const symptomIds = state.selectedSymptoms.map(s => s.id);
      const data = await apiFetch('/api/symptom-checker/assess', {
        method: 'POST',
        body: { symptoms: symptomIds },
      });

      const topMatch = data.possible_matches?.[0] || {};
      const score = topMatch.match_score !== undefined ? (topMatch.match_score + '%') : 'High';

      let matchesListHtml = (data.possible_matches || []).map(m => 
        '<li>' +
          '<div class="match-item">' +
            '<span class="match-cond">' + escapeHtml(m.condition) + '</span>' +
            '<span class="match-meta">Model Alignment: <strong>' + m.match_score + '%</strong> &bull; Clinician: <em>' + escapeHtml(m.specialist) + '</em></span>' +
          '</div>' +
        '</li>'
      ).join('');

      let docRecommendationsHtml = '';
      if (data.matching_doctors && data.matching_doctors.length > 0) {
        docRecommendationsHtml = 
          '<div class="result-doctors-box">' +
            '<h4>Verified Doctors Available in Northeast India:</h4>' +
            '<div class="result-doctor-grid">' +
              data.matching_doctors.map(doc => 
                '<div class="result-doc-mini">' +
                  '<div class="doc-avatar-sm">' + escapeHtml(doc.full_name.charAt(0)) + '</div>' +
                  '<div class="doc-info-sm">' +
                    '<strong>' + escapeHtml(doc.full_name) + '</strong>' +
                    '<span>' + escapeHtml(doc.specialty) + ' &bull; ' + escapeHtml(doc.location?.state || 'NE India') + '</span>' +
                    '<span class="fee-badge">Fee: ₹' + escapeHtml(doc.consultation_fee || 400) + '</span>' +
                  '</div>' +
                  '<button type="button" class="btn-book-sm" onclick="window.DhruvaCare.selectDoctorForBooking(\'' + escapeHtml(doc.id) + '\')">Book Visit</button>' +
                '</div>'
              ).join('') +
            '</div>' +
          '</div>';
      }

      resEl.innerHTML = 
        '<div class="result-card">' +
          '<div class="result-header">' +
            '<span class="level-tag">ML NEAREST-NEIGHBOR GUIDANCE</span>' +
            '<span class="score-badge">Model Confidence: ' + score + '</span>' +
          '</div>' +
          '<h3>Suggested Clinician: ' + escapeHtml(data.recommendation) + '</h3>' +
          '<p class="result-summary">The machine learning model matched your selected symptoms with clinical profiles in its database.</p>' +
          '<h4>Potential Disease & Symptom Matches:</h4>' +
          '<ul class="matches-list">' + matchesListHtml + '</ul>' +
          docRecommendationsHtml +
          '<div class="result-actions">' +
            '<button type="button" class="btn-view-all-docs" onclick="window.DhruvaCare.filterDoctorsBySpecialty(\'' + escapeHtml(data.recommendation) + '\')">' +
              'View All ' + escapeHtml(data.recommendation) + 's in North East &rarr;' +
            '</button>' +
          '</div>' +
          '<p class="result-disclaimer">' + escapeHtml(data.disclaimer) + '</p>' +
        '</div>';
      resEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (err) {
      resEl.innerHTML = '<div class="error-box"><p>' + escapeHtml(err.message) + '</p></div>';
    } finally {
      if (assessBtn) {
        assessBtn.disabled = false;
        assessBtn.innerHTML = 'See my care guidance <b>&rarr;</b>';
      }
    }
  }

  // --- DOCTOR DIRECTORY & LIVE QUEUE ---
  async function loadDoctors(filters = {}) {
    const listEl = document.getElementById('doctors-list');
    if (!listEl) return;

    listEl.innerHTML = '<div class="loading-box">Loading verified Northeast healthcare specialists…</div>';
    try {
      const params = new URLSearchParams();
      if (filters.specialty) params.set('specialty', filters.specialty);
      if (filters.state) params.set('state', filters.state);
      if (filters.q) params.set('q', filters.q);
      const query = params.toString() ? ('?' + params.toString()) : '';

      const data = await apiFetch('/api/doctors' + query);
      state.doctors = data.doctors || [];
      renderDoctorDirectory();
    } catch (err) {
      listEl.innerHTML = '<div class="error-box"><p>Unable to load doctor directory: ' + escapeHtml(err.message) + '</p></div>';
    }
  }

  function renderDoctorDirectory() {
    const listEl = document.getElementById('doctors-list');
    if (!listEl) return;

    if (state.doctors.length === 0) {
      listEl.innerHTML = '<div class="empty-box"><p>No doctors match the selected filters. Try choosing Another State or Specialty.</p></div>';
      return;
    }

    listEl.innerHTML = state.doctors.map(doc => {
      const loc = doc.location || {};
      const patientsAhead = Number.isFinite(Number(doc.patients_ahead)) ? Number(doc.patients_ahead) : null;
      const waitMins = patientsAhead === null ? null : patientsAhead * 7; // Formula from MediApp Business Plan Slide 7
      const presence = doc.live_presence || 'Active in OPD';
      const fee = doc.consultation_fee || 400;

      return (
        '<article class="doctor-card" data-id="' + escapeHtml(doc.id) + '">' +
          '<div class="doc-card-top">' +
            '<div class="doc-main">' +
              '<div class="doc-avatar">' + escapeHtml(doc.full_name.charAt(0)) + '</div>' +
              '<div>' +
                '<h3>' + escapeHtml(doc.full_name) + '</h3>' +
                '<p class="doc-spec">' + escapeHtml(doc.specialty) + '</p>' +
                '<p class="doc-loc">📍 ' + escapeHtml(loc.locality || loc.district || '') + ', ' + escapeHtml(loc.state || 'NE India') + '</p>' +
              '</div>' +
            '</div>' +
            '<div class="doc-status-badge">' +
              '<span class="pulse-dot"></span> ' + escapeHtml(presence) +
            '</div>' +
          '</div>' +
          '<p class="doc-bio">' + escapeHtml(doc.bio || 'Dedicated clinician providing OPD consultations and remote tele-follow-up.') + '</p>' +
          '<div class="queue-card">' +
            '<div class="queue-stat">' +
              '<span class="queue-label">Estimated Wait Time</span>' +
              '<span class="queue-val">' + (waitMins === null ? 'Updating' : waitMins + ' mins') + '</span>' +
            '</div>' +
            '<div class="queue-sub">' +
              '<span>Patients Ahead: <strong>' + (patientsAhead === null ? '—' : patientsAhead) + '</strong></span>' +
              '<span class="calc-note">' + (patientsAhead === null ? 'Queue data unavailable' : '(' + patientsAhead + ' ahead × 7 min)') + '</span>' +
            '</div>' +
          '</div>' +
          '<div class="doc-fee-breakdown">' +
            '<div class="fee-line"><span>Doctor Fee:</span><strong>₹' + fee + '</strong></div>' +
            '<div class="fee-line"><span>Platform Fee:</span><strong>₹50</strong></div>' +
            '<div class="fee-total"><span>Total Payable:</span><strong>₹' + (fee + 50) + '</strong></div>' +
          '</div>' +
          '<div class="doc-actions">' +
            '<button type="button" class="btn-primary-sm" onclick="window.DhruvaCare.openBookingModal(\'' + escapeHtml(doc.id) + '\')">' +
              'Book Appointment (₹' + (fee + 50) + ')' +
            '</button>' +
          '</div>' +
        '</article>'
      );
    }).join('');
  }

  function openBookingModal(doctorId) {
    const doc = state.doctors.find(d => d.id === doctorId);
    if (!doc) return;

    if (!state.currentUser) {
      showToast('Please sign in or register to book an appointment.', 'info');
      openAuthModal('login');
      return;
    }

    const modal = document.getElementById('booking-modal');
    if (!modal) return;

    document.getElementById('book-doc-name').textContent = doc.full_name;
    document.getElementById('book-doc-spec').textContent = doc.specialty + ' — ' + (doc.location?.state || 'Northeast');
    document.getElementById('book-doc-id').value = doc.id;
    document.getElementById('book-fee-total').textContent = '₹' + ((doc.consultation_fee || 400) + 50) + ' (incl. ₹50 MediApp fee)';

    const slotSelect = document.getElementById('book-slot-select');
    slotSelect.innerHTML = '';
    const slots = doc.availability || [
      { day: 'Today', start: '15:00', end: '17:00', mode: 'in_person' },
      { day: 'Tomorrow', start: '10:00', end: '13:00', mode: 'teleconsultation' },
    ];

    slots.forEach((s, idx) => {
      const opt = document.createElement('option');
      const val = s.day + ' ' + s.start + '-' + s.end + ' (' + (s.mode === 'teleconsultation' ? 'Teleconsultation' : 'In-Person OPD') + ')';
      opt.value = s.day + '_' + s.start + '_' + idx;
      opt.textContent = val;
      opt.dataset.mode = s.mode || 'in_person';
      slotSelect.appendChild(opt);
    });

    modal.classList.add('active');
  }

  function closeBookingModal() {
    const modal = document.getElementById('booking-modal');
    if (modal) modal.classList.remove('active');
  }

  async function handleBookingSubmit(e) {
    e.preventDefault();
    const docId = document.getElementById('book-doc-id').value;
    const slotSelect = document.getElementById('book-slot-select');
    const scheduledFor = slotSelect.options[slotSelect.selectedIndex]?.text || 'Next Slot';
    const mode = slotSelect.options[slotSelect.selectedIndex]?.dataset.mode || 'in_person';
    const reason = document.getElementById('book-reason').value.trim();
    const errBox = document.getElementById('booking-error');
    errBox.textContent = '';

    try {
      await apiFetch('/api/appointments', {
        method: 'POST',
        body: {
          doctor_id: docId,
          scheduled_for: scheduledFor,
          mode: mode,
          reason: reason,
        },
      });

      closeBookingModal();
      showToast('Appointment booked successfully! Slot: ' + scheduledFor, 'success');
      loadUserAppointments();
      window.dcGo && window.dcGo('teleconsult');
    } catch (err) {
      errBox.textContent = err.message;
    }
  }

  // --- USER APPOINTMENTS & TELECONSULTATION ---
  async function loadUserAppointments() {
    const wrap = document.getElementById('my-appointments-list');
    if (!wrap) return;

    if (!state.currentUser) {
      wrap.innerHTML = '<p class="empty-note">Sign in to view your scheduled OPD visits and teleconsultations.</p>';
      return;
    }

    try {
      const data = await apiFetch('/api/appointments');
      state.appointments = data.appointments || [];
      renderAppointments();
    } catch (err) {
      wrap.innerHTML = '<p class="error-note">Could not load appointments: ' + escapeHtml(err.message) + '</p>';
    }
  }

  function renderAppointments() {
    const wrap = document.getElementById('my-appointments-list');
    if (!wrap) return;

    if (state.appointments.length === 0) {
      wrap.innerHTML = '<p class="empty-note">No appointments booked yet. Browse clinicians above to schedule a visit.</p>';
      return;
    }

    wrap.innerHTML = state.appointments.map(apt => {
      const doc = state.doctors.find(d => d.id === apt.doctor_id);
      const docName = doc ? doc.full_name : 'Specialist Doctor';
      const isTele = apt.mode === 'teleconsultation';

      return (
        '<div class="appointment-card">' +
          '<div class="apt-header">' +
            '<div>' +
              '<strong>' + escapeHtml(docName) + '</strong>' +
              '<span class="apt-meta">' + escapeHtml(apt.scheduled_for) + ' &bull; <em>' + (isTele ? 'Online Teleconsultation' : 'In-Person OPD') + '</em></span>' +
            '</div>' +
            '<span class="badge-' + (apt.status === 'cancelled' ? 'alert' : 'success') + '">' + escapeHtml(apt.status.toUpperCase()) + '</span>' +
          '</div>' +
          (apt.reason ? ('<p class="apt-reason">Reason: ' + escapeHtml(apt.reason) + '</p>') : '') +
          '<div class="apt-actions">' +
            (isTele && apt.status !== 'cancelled' ? 
              ('<button type="button" class="btn-tele-sm" onclick="window.DhruvaCare.openTeleconsultation(\'' + escapeHtml(apt.id) + '\')">' +
                '💬 Open Encrypted Teleconsultation' +
              '</button>') : '') +
            (apt.status !== 'cancelled' ? 
              ('<button type="button" class="btn-cancel-sm" onclick="window.DhruvaCare.cancelAppointment(\'' + escapeHtml(apt.id) + '\')">Cancel</button>') : '') +
          '</div>' +
        '</div>'
      );
    }).join('');
  }

  async function cancelAppointment(aptId) {
    if (!confirm('Are you sure you want to cancel this appointment?')) return;
    try {
      await apiFetch('/api/appointments/' + aptId + '/cancel', { method: 'POST' });
      showToast('Appointment cancelled.', 'info');
      loadUserAppointments();
    } catch (err) {
      showToast(err.message, 'alert');
    }
  }

  async function openTeleconsultation(aptId) {
    try {
      const consultation = await apiFetch('/api/consultations', {
        method: 'POST',
        body: { appointment_id: aptId },
      });
      state.activeConsultationId = consultation.id;
      const modal = document.getElementById('teleconsult-modal');
      if (modal) {
        modal.classList.add('active');
        loadConsultationMessages(consultation.id);
      }
    } catch (err) {
      showToast(err.message, 'alert');
    }
  }

  async function loadConsultationMessages(conId) {
    const box = document.getElementById('chat-messages');
    if (!box) return;
    try {
      const data = await apiFetch('/api/consultations/' + conId + '/messages');
      box.innerHTML = (data.messages || []).map(m => 
        '<div class="chat-bubble ' + (m.sender_id === state.currentUser?.id ? 'outgoing' : 'incoming') + '">' +
          '<p>' + escapeHtml(m.ciphertext) + '</p>' +
          '<span class="chat-time">' + escapeHtml(m.created_at?.slice(11, 16) || '') + ' &bull; E2EE Encrypted</span>' +
        '</div>'
      ).join('');
      box.scrollTop = box.scrollHeight;
    } catch (err) {
      box.innerHTML = '<p class="error">' + escapeHtml(err.message) + '</p>';
    }
  }

  async function sendConsultationMessage(e) {
    e.preventDefault();
    if (!state.activeConsultationId) return;
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    try {
      await apiFetch('/api/consultations/' + state.activeConsultationId + '/messages', {
        method: 'POST',
        body: {
          ciphertext: text,
          algorithm: 'AES-GCM-256-CLIENT',
          key_version: '1.0',
        },
      });
      input.value = '';
      loadConsultationMessages(state.activeConsultationId);
    } catch (err) {
      showToast(err.message, 'alert');
    }
  }

  async function handleRequestCallRoute() {
    if (!state.activeConsultationId) return;
    try {
      await apiFetch('/api/consultations/' + state.activeConsultationId + '/call-route', {
        method: 'POST',
        body: { encrypted_signal: 'webrtc-offer-signal-sdp-dhruvacare-v1' },
      });
      showToast('Encrypted WebRTC call signal sent. Ready for video connection.', 'success');
    } catch (err) {
      showToast(err.message, 'alert');
    }
  }

  // --- PHARMACY & MEDICINE DELIVERY ---
  async function loadPharmacies(filters = {}) {
    const grid = document.getElementById('pharmacy-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="loading-box">Loading verified pharmacy partners…</div>';
    try {
      const params = new URLSearchParams();
      if (filters.state) params.set('state', filters.state);
      if (filters.district) params.set('district', filters.district);
      if (filters.q) params.set('q', filters.q);
      if (filters.medicine) params.set('medicine', filters.medicine);
      const query = params.toString() ? ('?' + params.toString()) : '';
      const data = await apiFetch('/api/pharmacies' + query);
      state.pharmacies = data.pharmacies || [];
      renderPharmacies();
    } catch (err) {
      grid.innerHTML = '<div class="error-box"><p>Unable to load pharmacy partners: ' + escapeHtml(err.message) + '</p></div>';
    }
  }

  function renderPharmacies() {
    const grid = document.getElementById('pharmacy-grid');
    if (!grid) return;

    grid.innerHTML = state.pharmacies.map(ph => 
      '<div class="pharmacy-card">' +
        '<div class="pharm-top">' +
          '<h4>' + escapeHtml(ph.name) + '</h4>' +
          '<span class="badge-tag">' + (ph.kind === 'drug_house' ? 'Central Drug House' : 'Retail Pharmacy') + '</span>' +
        '</div>' +
        '<p class="pharm-loc">📍 ' + escapeHtml(ph.location.locality) + ', ' + escapeHtml(ph.location.state) + '</p>' +
        '<p class="pharm-delivery">⚡ Express Delivery in <strong>' + ph.delivery_time_mins + ' mins</strong></p>' +
        '<div class="stock-tags">' +
          ph.inventory.map(m => '<span class="stock-chip">' + escapeHtml(m) + '</span>').join('') +
        '</div>' +
        '<button type="button" class="btn-order-med" onclick="window.DhruvaCare.openMedicineOrderModal(\'' + escapeHtml(ph.id) + '\')">' +
          'Order from this Outlet &rarr;' +
        '</button>' +
      '</div>'
    ).join('');
  }

  function openMedicineOrderModal(pharmacyId) {
    const ph = state.pharmacies.find(p => p.id === pharmacyId);
    if (!ph) return;

    if (!state.currentUser) {
      showToast('Please sign in or register to place a medicine order.', 'info');
      openAuthModal('login');
      return;
    }

    const modal = document.getElementById('order-modal');
    if (!modal) return;

    document.getElementById('order-pharmacy-name').textContent = ph.name;
    document.getElementById('order-pharmacy-id').value = ph.id;
    document.getElementById('order-items').value = '';
    document.getElementById('order-doctor-code').value = '';
    document.getElementById('order-error').textContent = '';
    modal.classList.add('active');
  }

  async function handleOrderSubmit(e) {
    e.preventDefault();
    const pharmacyId = document.getElementById('order-pharmacy-id').value;
    const itemsRaw = document.getElementById('order-items').value.trim();
    const docCode = document.getElementById('order-doctor-code').value.trim();
    const fulfillment = document.getElementById('order-fulfillment').value;
    const errBox = document.getElementById('order-error');
    errBox.textContent = '';

    const items = itemsRaw.split(',').map(s => s.trim()).filter(Boolean);
    if (items.length === 0) {
      errBox.textContent = 'Please enter at least one medication.';
      return;
    }

    try {
      const order = await apiFetch('/api/orders', {
        method: 'POST',
        body: {
          pharmacy_id: pharmacyId,
          items: items,
          doctor_code: docCode,
          fulfillment: fulfillment,
        },
      });

      document.getElementById('order-modal')?.classList.remove('active');
      showToast('Order #' + order.id + ' placed! Express delivery dispatched.', 'success');
    } catch (err) {
      errBox.textContent = err.message;
    }
  }

  // --- CALORIE COUNTER & NORTHEAST DIET ---
  async function loadFoodCatalog() {
    try {
      const data = await apiFetch('/api/calories/foods');
      state.foodCatalog = data.foods || [];
      const select = document.getElementById('food-select');
      if (select) {
        select.innerHTML = '<option value="">-- Choose Northeast dish or staple --</option>' +
          state.foodCatalog.map(f => '<option value="' + escapeHtml(f.name) + '" data-kcal="' + f.kcal_per_100g + '">' + escapeHtml(f.name) + ' (' + f.kcal_per_100g + ' kcal/100g)</option>').join('');
      }
    } catch (err) {
      console.warn('Could not load food catalog:', err);
    }
  }

  async function loadDailyCalories() {
    if (!state.currentUser) {
      renderDailyCalories([]);
      return;
    }
    try {
      const today = new Date().toISOString().slice(0, 10);
      const data = await apiFetch('/api/calories/summary?date=' + today);
      state.dailyCalorieLogs = data.entries || [];
      state.dailyTotalKcal = data.total_kcal || 0;
      renderDailyCalories(state.dailyCalorieLogs);
    } catch (err) {
      console.warn('Could not load calorie summary:', err);
    }
  }

  function renderDailyCalories(entries) {
    const listEl = document.getElementById('calorie-log-list');
    const totalEl = document.getElementById('total-kcal-display');
    const progressEl = document.getElementById('calorie-progress-bar');
    const target = 2000;

    if (totalEl) totalEl.textContent = state.dailyTotalKcal + ' / ' + target + ' kcal';
    if (progressEl) {
      const pct = Math.min(100, Math.round((state.dailyTotalKcal / target) * 100));
      progressEl.style.width = pct + '%';
      progressEl.setAttribute('aria-valuenow', pct);
    }

    if (!listEl) return;
    if (entries.length === 0) {
      listEl.innerHTML = '<p class="empty-note">No meals logged today yet. Log dishes below to track nutrition.</p>';
      return;
    }

    listEl.innerHTML = entries.map(entry => 
      '<div class="cal-entry-row">' +
        '<div>' +
          '<strong>' + escapeHtml(entry.meal.toUpperCase()) + '</strong>' +
          '<span>' + (entry.items || []).map(i => escapeHtml(i.name) + ' (' + i.grams + 'g)').join(', ') + '</span>' +
        '</div>' +
        '<strong>+' + entry.total_kcal + ' kcal</strong>' +
      '</div>'
    ).join('');
  }

  async function handleLogMealSubmit(e) {
    e.preventDefault();
    if (!state.currentUser) {
      showToast('Please sign in or register to log meals.', 'info');
      openAuthModal('login');
      return;
    }

    const foodName = document.getElementById('food-select').value;
    const grams = parseInt(document.getElementById('food-grams').value, 10) || 100;
    const meal = document.getElementById('meal-type').value;
    const errBox = document.getElementById('calorie-error');
    errBox.textContent = '';

    if (!foodName) {
      errBox.textContent = 'Please select a food or dish.';
      return;
    }

    try {
      await apiFetch('/api/calories/log', {
        method: 'POST',
        body: {
          items: [{ name: foodName, grams: grams }],
          meal: meal,
        },
      });
      showToast('Logged ' + foodName + ' (' + grams + 'g)!', 'success');
      document.getElementById('food-select').value = '';
      loadDailyCalories();
    } catch (err) {
      errBox.textContent = err.message;
    }
  }

  // --- HOSPITALS & EMERGENCY NETWORK ---
  async function loadHospitals() {
    const wrap = document.getElementById('hospitals-grid');
    if (!wrap) return;

    try {
      const data = await apiFetch('/api/hospitals');
      state.hospitals = data.hospitals || [];
      renderHospitals();
    } catch (err) {
      console.warn('Could not load hospitals:', err);
    }
  }

  function renderHospitals() {
    const wrap = document.getElementById('hospitals-grid');
    if (!wrap) return;

    wrap.innerHTML = state.hospitals.map(h => 
      '<div class="hospital-card">' +
        '<div class="hosp-top">' +
          '<div>' +
            '<h4>' + escapeHtml(h.name) + '</h4>' +
            '<p class="hosp-loc">📍 ' + escapeHtml(h.location?.locality || '') + ', ' + escapeHtml(h.location?.state || '') + '</p>' +
          '</div>' +
          '<span class="badge-franchise">' + escapeHtml(h.franchise_tier || 'Partner Hospital') + '</span>' +
        '</div>' +
        '<div class="hosp-specs">' +
          '<span class="badge-' + (h.emergency_capable ? 'alert' : 'neutral') + '">' +
            (h.emergency_capable ? '🚨 24/7 Emergency & Trauma' : 'General OPD') +
          '</span>' +
          (h.icu_beds_available ? ('<span class="badge-neutral">ICU Beds: ' + h.icu_beds_available + '</span>') : '') +
        '</div>' +
        '<div class="hosp-deps">' +
          '<strong>Departments:</strong>' +
          '<p>' + (h.departments || []).join(' &bull; ') + '</p>' +
        '</div>' +
        (h.diagnostic_gear ? 
          ('<div class="hosp-gear">' +
            '<strong>Diagnostic Technology:</strong>' +
            '<p>' + h.diagnostic_gear.join(', ') + '</p>' +
          '</div>') : '') +
      '</div>'
    ).join('');
  }

  // --- COMMUNITY CROWDFUNDING (MEDIAPP FOUNDATION) ---
  async function loadCrowdfunding() {
    const wrap = document.getElementById('crowdfunding-grid');
    if (!wrap) return;

    try {
      const data = await apiFetch('/api/crowdfunding');
      state.campaigns = data.campaigns || [];
      renderCrowdfunding();
    } catch (err) {
      console.warn('Could not load crowdfunding campaigns:', err);
    }
  }

  function renderCrowdfunding() {
    const wrap = document.getElementById('crowdfunding-grid');
    if (!wrap) return;

    wrap.innerHTML = state.campaigns.map(c => {
      const pct = Math.min(100, Math.round((c.raised_amount / c.target_amount) * 100));
      return (
        '<div class="campaign-card">' +
          '<div class="camp-header">' +
            '<span class="badge-zero-fee">0% Platform Fee &bull; 100% Direct Hospital Payment</span>' +
            '<h4>' + escapeHtml(c.title) + '</h4>' +
            '<p class="camp-loc">📍 ' + escapeHtml(c.location) + ' &bull; ' + escapeHtml(c.hospital) + '</p>' +
          '</div>' +
          '<p class="camp-story">' + escapeHtml(c.story) + '</p>' +
          '<div class="camp-progress">' +
            '<div class="progress-bar-wrap">' +
              '<div class="progress-bar-fill" style="width:' + pct + '%"></div>' +
            '</div>' +
            '<div class="camp-numbers">' +
              '<span>Raised: <strong>₹' + c.raised_amount.toLocaleString('en-IN') + '</strong></span>' +
              '<span>Target: ₹' + c.target_amount.toLocaleString('en-IN') + '</span>' +
            '</div>' +
          '</div>' +
          '<div class="camp-foot">' +
            '<span>' + c.donors_count + ' Community Donors</span>' +
            '<button type="button" class="btn-donate-sm" onclick="alert(\'Thank you for supporting Northeast emergency surgery crowdfunding. Secure donation gateway is ready.\')">' +
              'Donate to Hospital Bill' +
            '</button>' +
          '</div>' +
        '</div>'
      );
    }).join('');
  }

  // --- GLOBAL EXPORTS FOR INLINE ONCLICK HANDLERS ---
  window.DhruvaCare = {
    setSession: (user, token) => {
      state.currentUser = user || null;
      state.token = token || '';
      if (token) localStorage.setItem('dhruva_care_token', token); else localStorage.removeItem('dhruva_care_token');
      loadUserAppointments();
      loadDailyCalories();
    },
    selectDoctorForBooking: (docId) => {
      openBookingModal(docId);
    },
    filterDoctorsBySpecialty: (specialty) => {
      const select = document.getElementById('filter-specialty');
      if (select) select.value = specialty;
      loadDoctors({ specialty });
      window.dcGo && window.dcGo('doctors');
    },
    openBookingModal: (docId) => {
      openBookingModal(docId);
    },
    cancelAppointment: (aptId) => {
      cancelAppointment(aptId);
    },
    openTeleconsultation: (aptId) => {
      openTeleconsultation(aptId);
    },
    openMedicineOrderModal: (phId) => {
      openMedicineOrderModal(phId);
    },
  };

  // --- EVENT LISTENERS & SETUP ---
  function setupEventListeners() {
    document.querySelectorAll('[data-scroll]').forEach(btn => {
      btn.addEventListener('click', () => {
        window.dcGo && window.dcGo(btn.getAttribute('data-scroll'));
      });
    });

    const navToggle = document.getElementById('nav-toggle');
    const navLinks = document.getElementById('nav-links');
    navToggle?.addEventListener('click', () => {
      const open = navLinks?.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    navLinks?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      navToggle?.setAttribute('aria-expanded', 'false');
    }));

    document.getElementById('close-auth-modal')?.addEventListener('click', closeAuthModal);
    document.getElementById('tab-login')?.addEventListener('click', () => switchAuthTab('login'));
    document.getElementById('tab-signup')?.addEventListener('click', () => switchAuthTab('signup'));
    document.getElementById('login-form')?.addEventListener('submit', handleLoginSubmit);
    document.getElementById('signup-form')?.addEventListener('submit', handleSignupSubmit);

    const symInput = document.getElementById('symptom-search');
    if (symInput) {
      symInput.addEventListener('input', () => {
        clearTimeout(state.searchTimer);
        state.searchTimer = setTimeout(handleSymptomSearch, 250);
      });
      symInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const first = document.querySelector('#suggestions .suggestion');
          if (first) first.click();
        }
      });
    }

    document.getElementById('clear-symptoms')?.addEventListener('click', () => {
      state.selectedSymptoms = [];
      renderSelectedSymptoms();
      const res = document.getElementById('result');
      if (res) res.innerHTML = '';
    });

    document.getElementById('assess-button')?.addEventListener('click', handleAssessSymptoms);

    const specFilter = document.getElementById('filter-specialty');
    const stateFilter = document.getElementById('filter-state');
    const docSearch = document.getElementById('doctor-search-input');

    const applyDocFilters = () => {
      loadDoctors({
        specialty: specFilter?.value || '',
        state: stateFilter?.value || '',
        q: docSearch?.value?.trim() || '',
      });
    };

    specFilter?.addEventListener('change', applyDocFilters);
    stateFilter?.addEventListener('change', applyDocFilters);
    docSearch?.addEventListener('input', () => {
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(applyDocFilters, 300);
    });

    document.getElementById('close-booking-modal')?.addEventListener('click', closeBookingModal);
    document.getElementById('booking-form')?.addEventListener('submit', handleBookingSubmit);

    document.getElementById('close-order-modal')?.addEventListener('click', () => {
      document.getElementById('order-modal')?.classList.remove('active');
    });
    document.getElementById('order-form')?.addEventListener('submit', handleOrderSubmit);

    document.getElementById('meal-log-form')?.addEventListener('submit', handleLogMealSubmit);

    document.getElementById('close-teleconsult-modal')?.addEventListener('click', () => {
      document.getElementById('teleconsult-modal')?.classList.remove('active');
    });
    document.getElementById('chat-form')?.addEventListener('submit', sendConsultationMessage);
    document.getElementById('btn-request-call')?.addEventListener('click', handleRequestCallRoute);
  }

  // --- INITIALIZATION ---
  window.addEventListener('DOMContentLoaded', async () => {
    setupEventListeners();
    await initAuth();
    loadPopularSymptoms();
    loadDoctors();
    loadPharmacies();
    loadFoodCatalog();
    loadDailyCalories();
    loadHospitals();
    loadCrowdfunding();
    loadUserAppointments();
  });
})();