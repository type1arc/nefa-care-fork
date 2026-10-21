/* Dhruva Care — slide navigation, four-role sign-in and the Patient / Doctor / Hospital / Admin dashboards.
   Works alongside dhruva-care-integration.js (public features) and the Flask API. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  const KEY = 'dc_session', OLD_KEY = 'dhruva_care_token';
  let S = null, me = null, tab = null, acctKind = 'doctors', hospitals = [];
  try { S = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { S = null; }

  function toast(msg, type = 'info') {
    let c = $('#toast-container');
    if (!c) { c = document.createElement('div'); c.id = 'toast-container'; c.className = 'toast-container'; document.body.appendChild(c); }
    const t = document.createElement('div');
    t.className = 'toast toast-' + type; t.textContent = msg; c.appendChild(t);
    setTimeout(() => { t.classList.add('fade-out'); setTimeout(() => t.remove(), 400); }, 4000);
  }
  async function api(path, { method = 'GET', body } = {}) {
    const h = {}; let b;
    if (S) h.Authorization = 'Bearer ' + S.token;
    if (body instanceof FormData) b = body; else if (body) { h['Content-Type'] = 'application/json'; b = JSON.stringify(body); }
    const r = await fetch(path, { method, headers: h, body: b });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || 'Request failed (' + r.status + ')');
    return d;
  }
  const time = (iso) => (iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');

  /* ---------- slide router: one feature per screen ---------- */
  const FEATURES = [['symptom-check', 'AI Symptom Guide'], ['doctors', 'Verified Doctors'], ['pharmacy', 'Express Pharmacy'], ['diet', 'Diet & Calories'], ['hospitals', 'Hospitals'], ['teleconsult', 'Teleconsultation'], ['crowdfunding', 'Community Fund']];
  const LOGINS = ['patient', 'doctor', 'hospital', 'admin'].map((r) => 'login-' + r);
  const IDS = ['home', 'portal', 'login', ...LOGINS, ...FEATURES.map((f) => f[0])];
  function route() {
    let id = location.hash.slice(1);
    if (!IDS.includes(id)) id = 'home';
    if ((id === 'login' || id.startsWith('login-')) && S && me) { location.hash = 'portal'; return; }
    $$('.view').forEach((v) => v.classList.toggle('active', v.id === id));
    $$('.nav-links a').forEach((a) => a.classList.toggle('on', a.getAttribute('href') === '#' + id));
    window.scrollTo(0, 0);
    if (id === 'portal') renderPortal();
    if (id.startsWith('login-')) renderLoginPage(id.slice(6));
  }
  window.dcGo = (id) => { if (location.hash === '#' + id) route(); else location.hash = id; };
  function addPagers() {
    FEATURES.forEach(([id], i) => {
      const prev = FEATURES[i - 1], next = FEATURES[i + 1], wrap = $('#' + id + ' > .wrap');
      if (!wrap) return;
      wrap.insertAdjacentHTML('beforeend',
        '<nav class="pager" aria-label="Slide navigation"><a href="#' + (prev ? prev[0] : 'home') + '">← ' + (prev ? prev[1] : 'Home') + '</a>' +
        '<a class="pager-home" href="#home">All features</a>' +
        '<a href="#' + (next ? next[0] : 'home') + '">' + (next ? next[1] : 'Home') + ' →</a></nav>');
    });
  }

  /* ---------- four sign-in types ---------- */
  const STATES = ['Arunachal Pradesh', 'Assam', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland', 'Sikkim', 'Tripura'];
  const SPECS = ['General Medicine', 'Cardiology', 'Pediatrics', 'Dermatology', 'Orthopedic', 'Pulmonology', 'Neurology', 'Gynecology', 'ENT', 'Psychiatry', 'Ophthalmology'];
  const F = (name, label, type = 'text', o = {}) => ({ name, label, type, ...o });
  const ROLES = {
    patient: {
      label: 'Patient', icon: '🧑', blurb: 'Book doctors, track your queue, manage who sees your records.',
      loginHint: 'Sign in with your email and password.',
      login: { url: '/api/users/login', key: 'user', fields: [F('email', 'Email address', 'email', { ph: 'you@example.com' }), F('password', 'Password', 'password')] },
      signup: { url: '/api/users/signup', key: 'user', fields: [F('full_name', 'Full name', 'text', { full: 1 }), F('email', 'Email address', 'email'), F('phone', 'Phone number', 'tel'), F('password', 'Password', 'password', { min: 6 }), F('state', 'Northeast state', 'select', { options: STATES }), F('district', 'District / city', 'text', { full: 1 })] },
    },
    doctor: {
      label: 'Doctor', icon: '🩺', blurb: 'Mark presence, run your queue, view records patients approve.',
      loginHint: 'Doctors sign in with their State Medical Council number and NMR ID / UID.',
      login: { url: '/api/doctors/login', key: 'doctor', fields: [F('smc_number', 'State Medical Council (SMC) number', 'text', { full: 1, ph: 'e.g. ASM-MED-4412' }), F('nmr_id', 'NMR ID / UID', 'text', { full: 1 }), F('password', 'Password', 'password', { full: 1 })] },
      signup: { url: '/api/doctors/register', multipart: true, pending: true, fields: [F('full_name', 'Full name', 'text', { full: 1 }), F('email', 'Email address', 'email'), F('phone', 'Phone number', 'tel'), F('smc_number', 'SMC number'), F('nmr_id', 'NMR ID / UID'), F('specialty', 'Specialization', 'select', { options: SPECS, full: 1 }), F('password', 'Password (8+ characters)', 'password', { min: 8, full: 1 }), F('state', 'Practice state', 'select', { options: STATES }), F('district', 'District / city'), F('hospital_id', 'Affiliated hospital', 'select', { dyn: 'hospitals', optional: 1, full: 1 }), F('certificate', 'Registration certificate (PDF/image)', 'file', { full: 1 }), F('photo', 'Your photo', 'file', { full: 1 })] },
    },
    hospital: {
      label: 'Hospital', icon: '🏥', blurb: 'Reception desk: confirm doctors, manage the patient queue.',
      loginHint: 'Hospitals sign in with their registration / license number and HFR ID.',
      login: { url: '/api/hospitals/login', key: 'hospital', fields: [F('license_no', 'Hospital registration / license number', 'text', { full: 1 }), F('hfr_id', 'Health Facility Registry (HFR) ID', 'text', { full: 1 }), F('password', 'Password', 'password', { full: 1 })] },
      signup: { url: '/api/hospitals/register', multipart: true, pending: true, fields: [F('name', 'Hospital name', 'text', { full: 1 }), F('email', 'Reception email', 'email'), F('phone', 'Phone', 'tel'), F('license_no', 'Registration / license number'), F('hfr_id', 'HFR ID'), F('password', 'Password (8+ characters)', 'password', { min: 8, full: 1 }), F('state', 'State', 'select', { options: STATES }), F('district', 'District / city'), F('affiliated_to', 'Affiliated to (e.g. parent hospital)', 'text', { optional: 1, full: 1 }), F('departments', 'Departments (comma-separated)', 'text', { optional: 1, full: 1 }), F('emergency_capable', '24/7 emergency & trauma', 'checkbox', { optional: 1, full: 1 }), F('license', 'License document (PDF/image)', 'file', { full: 1 })] },
    },
    admin: {
      label: 'Admin', icon: '🛡️', blurb: 'Verify clinicians and hospitals, resolve support tickets.',
      loginHint: 'Server admins need their email, password and Admin ID code.',
      login: { url: '/api/admin/login', key: 'admin', fields: [F('email', 'Admin email', 'email', { full: 1 }), F('password', 'Password', 'password', { full: 1 }), F('admin_code', 'Admin ID code', 'password', { full: 1 })] },
    },
  };
  let authRole = 'patient', authMode = 'login';

  async function renderAuth() {
    const R = ROLES[authRole], cfg = R[authMode];
    $('#auth-mode').style.display = R.signup ? '' : 'none';
    $('#mode-login').classList.toggle('active', authMode === 'login');
    $('#mode-signup').classList.toggle('active', authMode === 'signup');
    $('#auth-title').textContent = R.icon + ' ' + R.label + (authMode === 'login' ? ' sign in' : ' registration');
    $('#auth-hint').textContent = authMode === 'login' ? R.loginHint : (cfg.pending ? 'Your application is reviewed by a Dhruva Care admin before you can sign in.' : 'Create your patient account.');
    $('#auth-error').textContent = '';
    $('#auth-submit').textContent = authMode === 'login' ? 'Sign in' : (cfg.pending ? 'Submit for verification' : 'Create account');
    if (cfg.fields.some((f) => f.dyn === 'hospitals') && !hospitals.length) {
      try { hospitals = (await api('/api/hospitals')).hospitals || []; } catch (e) { hospitals = []; }
    }
    $('#auth-fields').className = 'fgrid' + (authMode === 'signup' ? ' two' : '');
    $('#auth-fields').innerHTML = cfg.fields.map((f) => {
      const id = 'af-' + f.name, lab = esc(f.label) + (f.optional ? ' <i>(optional)</i>' : '');
      let ctl;
      if (f.type === 'select') {
        const opts = f.dyn === 'hospitals' ? hospitals.map((h) => [h.id, h.name + ' — ' + (h.location?.district || h.location?.state || '')]) : f.options.map((o) => [o, o]);
        ctl = '<select id="' + id + '" name="' + f.name + '" class="form-select"' + (f.optional ? '' : ' required') + '>' + (f.optional ? '<option value="">— None / independent —</option>' : '') + opts.map((o) => '<option value="' + esc(o[0]) + '">' + esc(o[1]) + '</option>').join('') + '</select>';
      } else if (f.type === 'checkbox') {
        return '<label class="check ' + (f.full ? 'full' : '') + '"><input type="checkbox" name="' + f.name + '" value="true"> ' + esc(f.label) + '</label>';
      } else if (f.type === 'file') {
        ctl = '<input id="' + id + '" name="' + f.name + '" type="file" accept=".pdf,image/*" class="form-input" required>';
      } else {
        ctl = '<input id="' + id + '" name="' + f.name + '" type="' + f.type + '" class="form-input" autocomplete="off"' + (f.min ? ' minlength="' + f.min + '"' : '') + (f.ph ? ' placeholder="' + esc(f.ph) + '"' : '') + (f.optional ? '' : ' required') + '>';
      }
      return '<div class="form-group ' + (f.full ? 'full' : '') + '"><label for="' + id + '">' + lab + '</label>' + ctl + '</div>';
    }).join('');
  }
  function renderLoginPage(role) {
    authRole = ROLES[role] ? role : 'patient';
    if (!ROLES[authRole].signup) authMode = 'login';
    $$('.auth-main').forEach((m) => { m.innerHTML = ''; });
    const box = $('.auth-main[data-role-page="' + authRole + '"]');
    if (!box) return;
    box.innerHTML = '<div class="modal-tabs" id="auth-mode" style="margin-right:0"><button type="button" class="modal-tab" id="mode-login">Sign in</button><button type="button" class="modal-tab" id="mode-signup">Register</button></div>' +
      '<h3 id="auth-title" style="margin:6px 0 4px"></h3><p id="auth-hint" class="modal-sub" style="margin-bottom:16px"></p>' +
      '<form id="auth-form" class="meal-form" autocomplete="off"><div id="auth-fields" class="fgrid"></div><button type="submit" id="auth-submit" class="btn-primary-sm">Sign in</button><div id="auth-error" class="modal-error"></div></form>';
    renderAuth();
  }
  function openAuth(role, mode = 'login') { authMode = mode; window.dcGo('login-' + (ROLES[role] ? role : 'patient')); }

  async function submitAuth(e) {
    e.preventDefault();
    const cfg = ROLES[authRole][authMode], err = $('#auth-error'), btn = $('#auth-submit');
    err.textContent = ''; btn.disabled = true;
    try {
      const form = e.target;
      let body;
      if (cfg.multipart) body = new FormData(form);
      else { body = {}; cfg.fields.forEach((f) => { const v = form.elements[f.name].value; body[f.name] = f.type === 'password' ? v : v.trim(); }); }
      const d = await api(cfg.url, { method: 'POST', body });
      if (cfg.pending) {
        $('#auth-fields').innerHTML = '<div class="done-box full">✅ <b>Application submitted.</b><br>A Dhruva Care admin will verify your documents and identifiers. You can sign in as soon as you are approved.</div>';
        $('#auth-submit').style.display = 'none';
        return;
      }
      const profile = d[ROLES[authRole].login.key];
      setSession(authRole, d.token, profile);
      toast('Welcome, ' + (profile.full_name || profile.name || profile.email) + '!', 'success');
      tab = null;
      if (location.hash === '#portal') route(); else window.dcGo('portal');
    } catch (ex) { err.textContent = ex.message; } finally { btn.disabled = false; }
  }

  function setSession(role, token, profile) {
    S = { token, role }; me = profile;
    localStorage.setItem(KEY, JSON.stringify(S));
    window.DhruvaCare?.setSession?.(role === 'patient' ? profile : null, role === 'patient' ? token : '');
    renderAcct();
  }
  function clearSession() {
    S = null; me = null; localStorage.removeItem(KEY);
    window.DhruvaCare?.setSession?.(null, '');
    renderAcct();
  }
  function renderAcct() {
    const a = $('#acct-area');
    if (!S || !me) { a.innerHTML = '<button type="button" class="header-action" data-go="login">Sign in</button>'; return; }
    const nm = me.full_name || me.name || me.email || 'Account';
    a.innerHTML = '<div class="user-badge"><div class="user-avatar">' + esc(nm.replace(/^Dr\.?\s*/i, '').charAt(0).toUpperCase()) + '</div>' +
      '<div class="user-info"><span class="user-name">' + esc(nm) + '</span><span class="user-loc">' + ROLES[S.role].label + '</span></div>' +
      '<button type="button" class="btn-ghost-sm" data-go="portal">Dashboard</button><button type="button" class="btn-ghost-sm" id="btn-signout">Log out</button></div>';
  }
  async function loadMe() {
    if (!S) return;
    const ep = { patient: '/api/users/me', doctor: '/api/doctors/me', hospital: '/api/hospitals/me', admin: '/api/admin/session' }[S.role];
    try { const d = await api(ep); me = S.role === 'admin' ? d.admin : d; if (S.role === 'patient') window.DhruvaCare?.setSession?.(me, S.token); }
    catch (e) { clearSession(); }
  }

  /* ---------- dashboards ---------- */
  const badge = (s) => '<span class="st st-' + esc(s) + '">' + esc(String(s).replace(/_/g, ' ')) + '</span>';
  const empty = (t) => '<p class="empty-note">' + t + '</p>';
  const card = (inner, cls = '') => '<div class="card pad ' + cls + '">' + inner + '</div>';

  const PORTALS = {
    patient: { tabs: [['care', 'My care'], ['consent', 'Records & consent'], ['support', 'Support']] },
    doctor: { tabs: [['today', 'Today'], ['records', 'Patient records'], ['support', 'Support']] },
    hospital: { tabs: [['reception', 'Reception'], ['queue', 'Queue'], ['support', 'Support']] },
    admin: { tabs: [['overview', 'Overview'], ['approvals', 'Approvals'], ['tickets', 'Tickets'], ['accounts', 'Accounts']] },
  };

  async function renderPortal() {
    const root = $('#portal-root');
    if (!S || !me) {
      root.innerHTML = '<div class="roles-grid">' + Object.entries(ROLES).map(([k, r]) => '<button class="role-card" data-role="' + k + '"><span>' + r.icon + '</span><b>' + r.label + '</b><small>' + r.blurb + '</small></button>').join('') + '</div>';
      return;
    }
    const P = PORTALS[S.role];
    if (!tab || !P.tabs.some((t) => t[0] === tab)) tab = P.tabs[0][0];
    const ids = { doctor: me.smc_number ? 'SMC ' + me.smc_number + ' · NMR ' + (me.nmr_id || '—') : '', hospital: 'Reg. ' + (me.license_no || '') + ' · HFR ' + (me.hfr_id || '—'), admin: me.email, patient: me.email };
    root.innerHTML = '<div class="sh"><p class="kicker">' + ROLES[S.role].label + ' dashboard</p><h2>' + esc(me.full_name || me.name || 'Welcome') + '</h2><p>' + esc(ids[S.role] || '') + '</p></div>' +
      '<div class="ptabs">' + P.tabs.map((t) => '<button class="ptab-btn' + (t[0] === tab ? ' active' : '') + '" data-tab="' + t[0] + '">' + t[1] + '</button>').join('') +
      '<button class="ptab-btn ghost" data-act="refresh">↻ Refresh</button></div><div id="ptab"><div class="loading-box">Loading…</div></div>';
    await loadTab();
  }
  async function loadTab() {
    const box = $('#ptab');
    if (!box) return;
    try { box.innerHTML = await TABS[S.role + '.' + tab](); }
    catch (e) { box.innerHTML = '<div class="error-box">' + esc(e.message) + '</div>'; }
  }

  function ticketsHtml(tickets, admin) {
    const form = admin ? '' : card('<h3>Raise a ticket</h3><p class="modal-sub" style="margin-bottom:12px">Facing any issue — billing, a booking, a doctor, a delivery, the app itself? Tell us and an admin will respond here.</p>' +
      '<form data-form="ticket" class="meal-form"><div class="form-row"><div class="form-group"><label>Category</label><select name="category" class="form-select"><option value="booking">Appointment / booking</option><option value="billing">Payment / billing</option><option value="medicine">Medicine order</option><option value="doctor">Doctor or hospital</option><option value="records">Records / privacy</option><option value="app">App problem</option><option value="other">Something else</option></select></div>' +
      '<div class="form-group"><label>Subject</label><input name="subject" class="form-input" required maxlength="120"></div></div>' +
      '<div class="form-group"><label>What happened?</label><textarea name="description" class="form-input" rows="4" required></textarea></div><button class="btn-primary-sm">Submit ticket</button></form>', 'mb');
    const list = tickets.length ? tickets.map((t) => card(
      '<div class="row-between"><b>' + esc(t.subject) + '</b>' + badge(t.status) + '</div><div class="modal-sub">' + esc(t.category) + ' · ' + (admin ? esc(t.role) + ' ' + esc(t.raised_by.slice(-6)) + ' · ' : '') + time(t.created_at) + '</div>' +
      '<p class="tk-body">' + esc(t.description) + '</p>' +
      (t.replies || []).map((r) => '<div class="reply ' + (r.by === 'admin' ? 'adm' : '') + '"><small>' + (r.by === 'admin' ? 'Dhruva Care team' : 'You') + ' · ' + time(r.at) + '</small>' + esc(r.message) + '</div>').join('') +
      '<form data-form="treply" data-id="' + t.id + '" class="chat-form" style="margin-top:10px"><input name="message" class="form-input" placeholder="Write a reply…" required><button class="btn-book-sm">Reply</button></form>' +
      (admin ? '<div class="btn-row" style="margin-top:10px">' + ['open', 'in_progress', 'resolved'].map((s) => '<button class="btn-chip' + (t.status === s ? ' on' : '') + '" data-act="tstatus" data-id="' + t.id + '" data-s="' + s + '">' + s.replace('_', ' ') + '</button>').join('') + '</div>' : ''), 'mb') ).join('') : empty(admin ? 'No tickets yet.' : 'You have not raised any tickets.');
    return form + '<h3 class="sub-h">' + (admin ? 'All tickets' : 'Your tickets') + '</h3>' + list;
  }

  const qRow = (q, actions, extra = '') => '<div class="qrow"><div class="tok">#' + q.token_no + '</div><div class="qmain"><b>' + esc(q.patient_name) + '</b><small>' + (q.source === 'online' ? 'Booked online' : 'Walk-in') + (q.phone ? ' · ' + esc(q.phone) : '') + (q.note ? ' · ' + esc(q.note) : '') + extra + '</small></div>' + badge(q.status) + '<div class="btn-row">' + actions + '</div></div>';
  const qBtns = (q) => q.status === 'waiting' ? '<button class="btn-chip" data-act="qs" data-id="' + q.id + '" data-s="in_consultation">Call in</button><button class="btn-chip" data-act="qs" data-id="' + q.id + '" data-s="no_show">No-show</button>' :
    q.status === 'in_consultation' ? '<button class="btn-chip on" data-act="qs" data-id="' + q.id + '" data-s="done">Mark done</button>' : '';

  const TABS = {
    /* ----- patient ----- */
    async 'patient.care'() {
      const o = await api('/api/patient/overview');
      const q = o.queue.length ? o.queue.map((x) => card('<div class="row-between"><b>Token #' + x.token_no + ' · ' + esc(x.doctor_name) + '</b>' + badge(x.status) + '</div><div class="modal-sub">' + esc(x.hospital_name || '') + '</div><div class="bigline">' + (x.status === 'in_consultation' ? "It's your turn" : x.patients_ahead + ' patient' + (x.patients_ahead === 1 ? '' : 's') + ' ahead · about ' + x.patients_ahead * 7 + ' min') + '</div>', 'mb')).join('') : empty("You are not in a hospital queue today. When the hospital adds your booked appointment to its queue, your live position shows up here.");
      return '<div class="two-col"><div>' + card('<span class="lbl-s">Your Patient ID</span><div class="pid">' + esc(o.user.patient_code) + '</div><p class="modal-sub">Give this ID to a doctor so they can request access to your records. Nothing is visible to them until you approve it.</p>', 'mb') +
        card('<h3>Quick actions</h3><div class="btn-row" style="margin-top:12px"><button class="btn-book-sm" data-go="doctors">Find a doctor</button><button class="btn-book-sm" data-go="teleconsult">My appointments</button><button class="btn-book-sm" data-go="pharmacy">Order medicine</button></div>') + '</div><div><h3 class="sub-h" style="margin-top:0">Today’s queue</h3>' + q + '</div></div>';
    },
    async 'patient.consent'() {
      const [o, rec] = await Promise.all([api('/api/patient/overview'), api('/api/users/me/records')]);
      const acc = o.access.length ? o.access.map((a) => card('<div class="row-between"><div><b>' + esc(a.doctor_name) + '</b><div class="modal-sub">' + esc(a.specialty) + ' · ' + time(a.updated_at) + '</div></div>' + badge(a.status) + '</div><div class="btn-row" style="margin-top:12px">' +
        (a.status === 'approved' ? '<button class="btn-cancel-sm" data-act="grant" data-id="' + a.doctor_id + '" data-ok="0">Revoke access</button>' : '<button class="btn-book-sm" data-act="grant" data-id="' + a.doctor_id + '" data-ok="1">Approve</button>' + (a.status === 'requested' ? '<button class="btn-cancel-sm" data-act="grant" data-id="' + a.doctor_id + '" data-ok="0">Deny</button>' : '')) + '</div>', 'mb')).join('') : empty('No doctor has asked to see your records.');
      const files = [...(rec.history_pdfs || []), ...(rec.consultation_pdfs || [])];
      return '<div class="two-col"><div><h3 class="sub-h" style="margin-top:0">Doctor access requests</h3>' + acc + '</div><div><h3 class="sub-h" style="margin-top:0">My records</h3>' +
        card('<form data-form="record" class="meal-form"><div class="form-row"><div class="form-group"><label>Type</label><select name="kind" class="form-select"><option value="history">Medical history</option><option value="consultation">Past consultation</option></select></div><div class="form-group"><label>Title</label><input name="title" class="form-input" required></div></div><div class="form-group"><label>PDF or image</label><input type="file" name="file" accept=".pdf,image/*" class="form-input" required></div><button class="btn-primary-sm">Upload record</button></form>', 'mb') +
        (files.length ? files.map((f) => '<div class="listline"><b>' + esc(f.title) + '</b><small>' + time(f.uploaded_at) + '</small></div>').join('') : empty('No records uploaded yet.')) + '</div></div>';
    },
    /* ----- doctor ----- */
    async 'doctor.today'() {
      const [d, h, qq] = await Promise.all([api('/api/doctors/me'), api('/api/hospitals'), api('/api/doctors/me/queue')]);
      me = { ...me, ...d };
      const p = d.presence, step = (ok, label) => '<div class="step ' + (ok ? 'ok' : '') + '"><i>' + (ok ? '✓' : '•') + '</i>' + label + '</div>';
      const queue = qq.queue.filter((q) => q.status !== 'removed');
      return '<div class="two-col"><div>' + card('<h3>Hospital affiliation</h3><form data-form="affil" class="chat-form" style="margin-top:10px"><select name="hospital_id" class="form-select"><option value="">— Not linked —</option>' + (h.hospitals || []).map((x) => '<option value="' + x.id + '"' + (x.id === d.hospital_id ? ' selected' : '') + '>' + esc(x.name) + '</option>').join('') + '</select><button class="btn-book-sm">Save</button></form>', 'mb') +
        card('<h3>Presence today</h3><p class="modal-sub">Patients only see you as available once <b>you and the hospital reception both</b> confirm.</p><div class="steps">' + step(p.doctor_marked, 'You marked yourself present') + step(p.hospital_marked, 'Hospital reception confirmed you') + '</div>' +
          (p.confirmed ? '<div class="ok-banner">Confirmed — patients see you as available at ' + esc(d.hospital_name) + '</div>' : '<div class="wait-banner">Not visible as available yet</div>') +
          '<button class="' + (p.doctor_marked ? 'btn-cancel-sm' : 'btn-primary-sm') + '" style="margin-top:12px" data-act="docpresence" data-present="' + (p.doctor_marked ? 0 : 1) + '">' + (p.doctor_marked ? 'Unmark my presence' : "I'm present — mark me") + '</button>') + '</div>' +
        '<div><h3 class="sub-h" style="margin-top:0">Today’s queue</h3>' + (queue.length ? queue.map((q) => qRow(q, qBtns(q))).join('') : empty('Nobody is in your queue yet. Hospital reception adds patients.')) + '</div></div>';
    },
    async 'doctor.records'() {
      const o = await api('/api/doctors/me/patients');
      return '<div class="two-col"><div>' + card('<h3>Request patient access</h3><p class="modal-sub" style="margin-bottom:10px">Ask the patient for their Patient ID. They must approve before you can see anything.</p><form data-form="request" class="chat-form"><input name="patient_code" class="form-input" placeholder="PT-XXXXXXXX" required><button class="btn-book-sm">Request</button></form>', 'mb') +
        '<h3 class="sub-h">My patients</h3>' + (o.patients.length ? o.patients.map((p) => '<div class="listline"><div><b>' + esc(p.full_name) + '</b><small>' + time(p.updated_at) + '</small></div>' + badge(p.status) + (p.status === 'approved' ? '<button class="btn-book-sm" data-act="viewpt" data-id="' + p.patient_id + '">View records</button>' : '') + '</div>').join('') : empty('No access requests yet.')) +
        '</div><div id="ptview">' + empty('Select an approved patient to view their profile and records.') + '</div></div>';
    },
    /* ----- hospital ----- */
    async 'hospital.reception'() {
      const r = await api('/api/hospital/roster');
      return '<p class="modal-sub" style="margin-bottom:14px">A doctor shows as available to patients only after <b>both</b> the doctor and this desk mark them present.</p>' +
        (r.doctors.length ? r.doctors.map((d) => card('<div class="row-between"><div><b>' + esc(d.full_name) + '</b><div class="modal-sub">' + esc(d.specialty) + ' · SMC ' + esc(d.smc_number) + '</div></div>' + (d.presence.confirmed ? badge('confirmed') : badge('pending')) + '</div>' +
          '<div class="steps" style="margin:12px 0"><div class="step ' + (d.presence.doctor_marked ? 'ok' : '') + '"><i>' + (d.presence.doctor_marked ? '✓' : '•') + '</i>Doctor marked</div><div class="step ' + (d.presence.hospital_marked ? 'ok' : '') + '"><i>' + (d.presence.hospital_marked ? '✓' : '•') + '</i>Desk marked</div></div>' +
          '<div class="row-between"><span class="modal-sub">' + d.waiting + ' waiting in queue</span><button class="' + (d.presence.hospital_marked ? 'btn-cancel-sm' : 'btn-book-sm') + '" data-act="hospresence" data-id="' + d.id + '" data-present="' + (d.presence.hospital_marked ? 0 : 1) + '">' + (d.presence.hospital_marked ? 'Unmark' : 'Mark present') + '</button></div>', 'mb')).join('') : empty('No doctors are linked to your hospital yet. Doctors link themselves from their dashboard (Today → Hospital affiliation).'));
    },
    async 'hospital.queue'() {
      const [r, q] = await Promise.all([api('/api/hospital/roster'), api('/api/hospital/queue')]);
      const opts = r.doctors.map((d) => '<option value="' + d.id + '">' + esc(d.full_name) + '</option>').join('');
      const byDoc = {};
      q.queue.forEach((e) => (byDoc[e.doctor_id] = byDoc[e.doctor_id] || []).push(e));
      return '<div class="two-col"><div>' + card('<h3>Add a walk-in</h3><form data-form="walkin" class="meal-form"><div class="form-group"><label>Doctor</label><select name="doctor_id" class="form-select" required>' + opts + '</select></div><div class="form-row"><div class="form-group"><label>Patient name</label><input name="patient_name" class="form-input" required></div><div class="form-group"><label>Phone</label><input name="phone" class="form-input"></div></div><div class="form-group"><label>Note</label><input name="note" class="form-input"></div><button class="btn-primary-sm"' + (r.doctors.length ? '' : ' disabled') + '>Add to queue</button></form>', 'mb') +
        '<h3 class="sub-h">Booked online — not yet queued</h3>' + (q.online_appointments.length ? q.online_appointments.map((a) => card('<div class="row-between"><div><b>' + esc(a.patient_name) + '</b><div class="modal-sub">' + esc(a.doctor_name) + ' · ' + esc(a.scheduled_for) + '</div>' + (a.reason ? '<div class="modal-sub">“' + esc(a.reason) + '”</div>' : '') + '</div><button class="btn-book-sm" data-act="queueapt" data-id="' + a.id + '">Add to queue</button></div>', 'mb')).join('') : empty('No online bookings waiting.')) +
        '</div><div><h3 class="sub-h" style="margin-top:0">Live queues</h3>' + (r.doctors.length ? r.doctors.map((d) => { const rows = byDoc[d.id] || []; return card('<div class="row-between"><b>' + esc(d.full_name) + '</b>' + (d.presence.confirmed ? badge('confirmed') : badge('pending')) + '</div>' + (rows.length ? rows.map((e) => qRow(e, qBtns(e))).join('') : empty('Queue is empty.')), 'mb'); }).join('') : empty('No doctors linked yet.')) + '</div></div>';
    },
    /* ----- admin ----- */
    async 'admin.overview'() {
      const [d, t] = await Promise.all([api('/api/admin/dashboard'), api('/api/tickets?status=open')]);
      const s = (n, l, sub) => card('<div class="stat-n">' + n + '</div><b>' + l + '</b><div class="modal-sub">' + sub + '</div>');
      return '<div class="stat-grid">' + s(d.users.total, 'Patients', d.users.active + ' active') + s(d.doctors.verified, 'Verified doctors', d.doctors.pending + ' pending') + s(d.hospitals.verified, 'Verified hospitals', d.hospitals.pending + ' pending') + s(d.pharmacies.verified, 'Verified pharmacies', d.pharmacies.pending + ' pending') + s(d.appointments_today_total, 'Appointments', d.open_orders + ' open orders') + s(t.tickets.length, 'Open tickets', 'need a reply') + '</div>';
    },
    async 'admin.approvals'() {
      const [d, h] = await Promise.all([api('/api/admin/doctors/pending'), api('/api/admin/hospitals/pending')]);
      const btns = (kind, id) => '<div class="btn-row" style="margin-top:12px"><button class="btn-book-sm" data-act="review" data-kind="' + kind + '" data-id="' + id + '" data-do="approve">Approve</button><button class="btn-cancel-sm" data-act="review" data-kind="' + kind + '" data-id="' + id + '" data-do="reject">Reject</button></div>';
      const tick = (v) => (v ? '✓' : '✗ missing');
      return '<h3 class="sub-h" style="margin-top:0">Doctors awaiting verification</h3>' + (d.pending.length ? d.pending.map((x) => card('<b>' + esc(x.full_name) + '</b> · ' + esc(x.specialty) + '<div class="modal-sub">SMC ' + esc(x.smc_number || x.registration_no) + ' · NMR ' + esc(x.nmr_id || '—') + ' · ' + esc(x.email) + '</div><div class="modal-sub">' + esc(x.practice_location?.district || '') + ', ' + esc(x.practice_location?.state || '') + ' · Certificate ' + tick(x.documents?.certificate) + ' · Photo ' + tick(x.documents?.photo) + '</div>' + btns('doctors', x.id), 'mb')).join('') : empty('No pending doctors.')) +
        '<h3 class="sub-h">Hospitals awaiting verification</h3>' + (h.pending.length ? h.pending.map((x) => card('<b>' + esc(x.name) + '</b>' + (x.affiliated_to ? ' · affiliated to ' + esc(x.affiliated_to) : '') + '<div class="modal-sub">Reg. ' + esc(x.license_no) + ' · HFR ' + esc(x.hfr_id || '—') + ' · ' + esc(x.email) + '</div><div class="modal-sub">' + esc(x.location?.district || '') + ', ' + esc(x.location?.state || '') + ' · License ' + tick(x.license_document) + '</div>' + btns('hospitals', x.id), 'mb')).join('') : empty('No pending hospitals.'));
    },
    async 'admin.tickets'() { return ticketsHtml((await api('/api/tickets')).tickets, true); },
    async 'admin.accounts'() {
      const d = await api('/api/admin/accounts/' + acctKind);
      const one = { users: 'user', doctors: 'doctor', hospitals: 'hospital' }[acctKind];
      return '<div class="btn-row" style="margin-bottom:14px">' + ['users', 'doctors', 'hospitals'].map((k) => '<button class="btn-chip' + (k === acctKind ? ' on' : '') + '" data-act="kind" data-k="' + k + '">' + k + '</button>').join('') + '</div>' +
        (d.items.length ? d.items.map((x) => '<div class="listline"><div><b>' + esc(x.full_name || x.name) + '</b><small>' + esc(x.email || '') + '</small></div>' + badge(x.status || 'active') + (x.status === 'suspended' ? '<button class="btn-book-sm" data-act="mod" data-kind="' + one + '" data-id="' + x.id + '" data-do="restore">Restore</button>' : '<button class="btn-cancel-sm" data-act="mod" data-kind="' + one + '" data-id="' + x.id + '" data-do="suspend">Suspend</button>') + '</div>').join('') : empty('Nothing here.'));
    },
  };
  ['patient', 'doctor', 'hospital'].forEach((r) => { TABS[r + '.support'] = async () => ticketsHtml((await api('/api/tickets')).tickets, false); });

  const post = (url, body) => api(url, { method: 'POST', body: body || {} });
  const ACTS = {
    refresh: () => {},
    grant: async (el) => { await post('/api/users/me/doctors/' + el.dataset.id + '/access', { approved: el.dataset.ok === '1' }); toast(el.dataset.ok === '1' ? 'Access approved' : 'Access removed', 'success'); },
    docpresence: async (el) => { await post('/api/doctors/me/presence', { present: el.dataset.present === '1' }); },
    hospresence: async (el) => { await post('/api/hospital/doctors/' + el.dataset.id + '/presence', { present: el.dataset.present === '1' }); },
    queueapt: async (el) => { await post('/api/hospital/queue/from-appointment', { appointment_id: el.dataset.id }); toast('Added to the queue', 'success'); },
    qs: async (el) => { await post((S.role === 'doctor' ? '/api/doctors/me/queue/' : '/api/hospital/queue/') + el.dataset.id + '/status', { status: el.dataset.s }); },
    tstatus: async (el) => { await post('/api/tickets/' + el.dataset.id + '/status', { status: el.dataset.s }); },
    kind: (el) => { acctKind = el.dataset.k; },
    mod: async (el) => { await post('/api/admin/accounts/' + el.dataset.kind + '/' + el.dataset.id + '/' + el.dataset.do, { note: '' }); },
    review: async (el) => {
      let note = '';
      if (el.dataset.do === 'reject') { note = prompt('Reason for rejection (shown in the record):') || ''; if (note === '') return; }
      await post('/api/admin/' + el.dataset.kind + '/' + el.dataset.id + '/' + el.dataset.do, { note });
      toast('Application ' + el.dataset.do + 'd', 'success');
    },
    viewpt: async (el) => {
      const box = $('#ptview'); box.innerHTML = '<div class="loading-box">Loading…</div>';
      try {
        const p = await api('/api/doctors/me/patients/' + el.dataset.id);
        const prof = Object.entries(p.medical_profile || {}).map(([k, v]) => '<div class="kv"><span>' + esc(k.replace(/_/g, ' ')) + '</span><b>' + esc(typeof v === 'object' ? JSON.stringify(v) : v) + '</b></div>').join('');
        const recs = [...(p.medical_records?.history_pdfs || []), ...(p.medical_records?.consultation_pdfs || [])].map((f) => '<div class="listline"><b>' + esc(f.title) + '</b><small>' + time(f.uploaded_at) + '</small></div>').join('');
        const notes = (p.medical_records?.notes || []).map((n) => '<div class="listline"><b>' + esc(typeof n === 'object' ? (n.text || JSON.stringify(n)) : n) + '</b></div>').join('');
        box.innerHTML = card('<div class="row-between"><h3>' + esc(p.full_name) + '</h3>' + badge('approved') + '</div><div class="modal-sub">' + [p.age && p.age + ' yrs', p.sex, p.phone, p.location?.district && p.location.district + ', ' + p.location.state].filter(Boolean).map(esc).join(' · ') + '</div>' +
          '<h4 class="sub-h">Medical profile</h4>' + (prof || empty('Nothing recorded.')) + '<h4 class="sub-h">Records</h4>' + (recs || empty('No uploaded records.')) + (notes ? '<h4 class="sub-h">Notes</h4>' + notes : '') + '<p class="modal-sub" style="margin-top:12px">Shown because the patient approved your access. They can revoke it at any time.</p>');
      } catch (e) { box.innerHTML = '<div class="error-box">' + esc(e.message) + '</div>'; }
    },
  };
  const FORMS = {
    ticket: async (f) => { await post('/api/tickets', Object.fromEntries(new FormData(f))); toast('Ticket raised — we will reply here', 'success'); },
    treply: async (f) => { await post('/api/tickets/' + f.dataset.id + '/reply', Object.fromEntries(new FormData(f))); },
    record: async (f) => { await api('/api/users/me/records', { method: 'POST', body: new FormData(f) }); toast('Record uploaded', 'success'); },
    affil: async (f) => { await api('/api/doctors/me/hospital', { method: 'PUT', body: Object.fromEntries(new FormData(f)) }); toast('Affiliation saved', 'success'); },
    request: async (f) => { const r = await post('/api/doctors/me/access-requests', Object.fromEntries(new FormData(f))); toast(r.status === 'approved' ? 'You already have access' : 'Request sent — waiting for the patient', 'success'); },
    walkin: async (f) => { const r = await post('/api/hospital/queue', Object.fromEntries(new FormData(f))); toast('Added as token #' + r.token_no, 'success'); },
  };

  function wire() {
    document.addEventListener('click', async (e) => {
      const go = e.target.closest('[data-go]'); if (go) { window.dcGo(go.dataset.go); return; }
      const role = e.target.closest('[data-role]'); if (role) { openAuth(role.dataset.role); return; }
      const md = e.target.closest('#mode-login,#mode-signup'); if (md) { authMode = md.id === 'mode-signup' ? 'signup' : 'login'; renderLoginPage(authRole); return; }
      if (e.target.closest('#btn-signout')) { try { await api('/api/users/logout', { method: 'POST' }); } catch (x) { /* already signed out */ } clearSession(); toast('Signed out', 'info'); window.dcGo('home'); return; }
      const tb = e.target.closest('[data-tab]'); if (tb) { tab = tb.dataset.tab; renderPortal(); return; }
      const act = e.target.closest('[data-act]');
      if (act && ACTS[act.dataset.act]) {
        act.disabled = true;
        try { await ACTS[act.dataset.act](act); if (act.dataset.act !== 'viewpt') await loadTab(); else act.disabled = false; }
        catch (x) { toast(x.message, 'alert'); act.disabled = false; }
      }
    });
    document.addEventListener('submit', async (e) => {
      if (e.target.id === 'auth-form') { submitAuth(e); return; }
      const f = e.target.closest('[data-form]'); if (!f) return;
      e.preventDefault();
      try { await FORMS[f.dataset.form](f); if (f.dataset.form !== 'record') f.reset(); await loadTab(); }
      catch (x) { toast(x.message, 'alert'); }
    });
    window.addEventListener('dc:need-login', (e) => openAuth(e.detail?.role || 'patient'));
    window.addEventListener('hashchange', route);
    const nt = $('#nav-toggle'), nl = $('#nav-links');
    nt?.addEventListener('click', () => nt.setAttribute('aria-expanded', nl.classList.toggle('open') ? 'true' : 'false'));
    $$('.nav-links a').forEach((a) => a.addEventListener('click', () => { nl.classList.remove('open'); nt?.setAttribute('aria-expanded', 'false'); }));
  }

  window.addEventListener('DOMContentLoaded', async () => {
    addPagers(); wire(); renderAcct();
    await loadMe(); renderAcct(); route();
  });
})();
