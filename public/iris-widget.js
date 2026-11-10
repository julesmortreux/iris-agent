/**
 * Widget Iris : assistant de recherche de contacts, en JavaScript pur.
 * Intégration : <script src=".../iris-widget.js" data-api="https://hote-du-service"></script>
 * Sans data-api, le service est appelé sur le domaine de la page.
 */
(function () {
  'use strict';

  var scriptTag = document.currentScript;
  var API_URL = ((scriptTag && scriptTag.getAttribute('data-api')) || '').replace(/\/$/, '');
  var history = [];
  var shownIds = [];   // contacts déjà affichés, exclus des résultats suivants
  var loading = false;
  var open = false;

  /* ============================ STYLES ============================ */
  var CSS = [
    '#IW,#IW *{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;}',

    '#IW-fab{position:fixed;bottom:26px;right:26px;z-index:2147483000;display:flex;align-items:center;gap:10px;',
    '  height:56px;padding:0 22px 0 18px;border:none;border-radius:32px;cursor:pointer;',
    '  background:var(--iris-primary,#0070AD);color:#fff;font-size:15px;font-weight:600;letter-spacing:.2px;',
    '  box-shadow:0 8px 26px rgba(22,35,61,.32);transition:transform .22s cubic-bezier(.4,0,.2,1),box-shadow .22s;}',
    '#IW-fab:hover{transform:translateY(-2px);box-shadow:0 12px 32px rgba(22,35,61,.4);}',
    '#IW-fab .fav{width:32px;height:32px;margin-left:-6px;display:flex;flex-shrink:0;}',
    '#IW-fab .fav svg{width:100%;height:100%;}',
    '#IW-fab.hide{opacity:0;pointer-events:none;transform:scale(.85);}',

    '#IW-panel{position:fixed;bottom:26px;right:26px;z-index:2147483001;width:412px;max-width:calc(100vw - 32px);',
    '  height:640px;max-height:calc(100vh - 52px);background:#fff;border-radius:18px;overflow:hidden;',
    '  display:flex;flex-direction:column;border:1px solid var(--iris-border,#DDE6EE);',
    '  box-shadow:0 24px 60px rgba(16,29,54,.28),0 4px 14px rgba(16,29,54,.12);',
    '  opacity:0;pointer-events:none;transform:translateY(16px) scale(.98);transform-origin:bottom right;',
    '  transition:opacity .26s cubic-bezier(.4,0,.2,1),transform .26s cubic-bezier(.4,0,.2,1);}',
    '#IW-panel.show{opacity:1;pointer-events:auto;transform:translateY(0) scale(1);}',

    '#IW-head{background:linear-gradient(135deg,var(--iris-primary,#0070AD),var(--iris-primary-strong,#005A8C));padding:18px 20px;display:flex;align-items:center;gap:13px;flex-shrink:0;}',
    '#IW-head .av{width:42px;height:42px;flex-shrink:0;border-radius:50%;overflow:hidden;box-shadow:0 0 0 1px rgba(255,255,255,.16);}',
    '#IW-head .av svg{width:100%;height:100%;display:block;}',
    '#IW-head .info{flex:1;min-width:0;}',
    '#IW-head .info b{display:block;color:#fff;font-size:15.5px;font-weight:600;line-height:1.2;}',
    '#IW-head .info span{display:flex;align-items:center;gap:6px;color:var(--iris-on-primary-soft,#D6ECF7);font-size:12px;margin-top:2px;}',
    '#IW-dot{width:7px;height:7px;border-radius:50%;background:#94a3b8;transition:background .4s,box-shadow .4s;}',
    '#IW-dot.ok{background:var(--iris-ok,#12ABDB);box-shadow:0 0 0 3px rgba(62,207,142,.2);}',
    '#IW-x{background:none;border:none;color:var(--iris-on-primary-soft,#D6ECF7);cursor:pointer;width:34px;height:34px;border-radius:9px;',
    '  display:flex;align-items:center;justify-content:center;transition:background .18s,color .18s;flex-shrink:0;}',
    '#IW-x:hover{background:rgba(255,255,255,.1);color:#fff;}',
    '#IW-x svg{width:18px;height:18px;}',

    '#IW-chat{flex:1;overflow-y:auto;padding:28px 22px;display:flex;flex-direction:column;gap:22px;background:var(--iris-surface,#F5F9FC);}',
    '#IW-chat::-webkit-scrollbar{width:6px;}',
    '#IW-chat::-webkit-scrollbar-thumb{background:#d3dae5;border-radius:8px;}',
    '.IW-m{display:flex;flex-direction:column;max-width:100%;animation:iwIn .32s ease both;}',
    '@keyframes iwIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}',
    '.IW-m.u{align-items:flex-end;}',
    '.IW-m.a{align-items:flex-start;}',
    '.IW-b{font-size:14px;line-height:1.65;}',
    '.IW-m.u .IW-b{background:linear-gradient(135deg,var(--iris-primary-strong,#005A8C),var(--iris-primary,#0070AD));color:#fff;border-radius:18px 18px 5px 18px;',
    '  padding:15px 20px !important;max-width:74%;box-shadow:0 3px 10px rgba(22,35,61,.2);}',
    '.IW-m.a .IW-b{color:var(--iris-text,#1F2A37);max-width:100%;width:100%;}',
    '.IW-b p{margin:0 0 12px;}.IW-b p:last-child{margin:0;}',
    '.IW-b strong{font-weight:600;color:var(--iris-primary,#0070AD);}',
    '.IW-b a.inl{color:var(--iris-link,#0070AD);text-decoration:none;font-weight:500;border-bottom:1px solid rgba(45,90,140,.3);}',
    '.IW-b a.inl:hover{border-bottom-color:var(--iris-link,#0070AD);}',

    '.IW-card{background:#fff;border:1px solid var(--iris-border,#DDE6EE);border-radius:12px;padding:18px 20px;margin:14px 0;',
    '  display:flex;gap:15px;transition:border-color .18s,box-shadow .18s;}',
    '.IW-b p + .IW-card{margin-top:20px;}',
    '.IW-card:hover{border-color:#c9d3e2;box-shadow:0 6px 18px rgba(16,29,54,.08);}',
    '.IW-card .ini{width:44px;height:44px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;',
    '  background:var(--iris-tint,#E6F4FA);color:var(--iris-link,#0070AD);font-weight:600;font-size:15px;letter-spacing:.3px;}',
    '.IW-card .body{flex:1;min-width:0;}',
    '.IW-card .nm{font-weight:600;font-size:14.5px;color:var(--iris-primary,#0070AD);line-height:1.3;}',
    '.IW-card .rl{font-size:13px;color:var(--iris-text-soft,#5B6B7C);line-height:1.5;margin-top:3px;}',
    '.IW-card .meta{font-size:12px;color:#8a95a6;line-height:1.5;margin-top:6px;}',
    '.IW-card .badges{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;}',
    '.IW-card .bdg{font-size:11px;font-weight:600;letter-spacing:.2px;padding:3px 9px;border-radius:20px;',
    '  background:var(--iris-tint,#E6F4FA);color:var(--iris-link,#0070AD);}',
    '.IW-card .bdg.al{background:#e9f6ef;color:#1f8a5b;}',
    '.IW-card .act{display:inline-flex;align-items:center;gap:6px;margin-top:10px;font-size:12.5px;font-weight:600;',
    '  color:var(--iris-link,#0070AD);text-decoration:none;padding:6px 12px;border:1px solid var(--iris-border,#DDE6EE);border-radius:8px;transition:all .18s;}',
    '.IW-card .act:hover{background:#f2f6fc;border-color:var(--iris-link,#0070AD);}',
    '.IW-card .act svg{width:14px;height:14px;}',

    '#IW-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px;}',
    '#IW-chips button{font-size:12.5px;color:var(--iris-link,#0070AD);background:#fff;border:1px solid var(--iris-border,#DDE6EE);border-radius:20px;',
    '  padding:7px 13px;cursor:pointer;transition:all .18s;font-weight:500;}',
    '#IW-chips button:hover{background:#f2f6fc;border-color:var(--iris-link,#0070AD);}',

    '.IW-dots{display:flex;gap:5px;padding:6px 2px;}',
    '.IW-dots i{width:7px;height:7px;border-radius:50%;background:#b3c0d4;animation:iwPulse 1.3s infinite ease-in-out;}',
    '.IW-dots i:nth-child(1){animation-delay:-.32s}.IW-dots i:nth-child(2){animation-delay:-.16s}',
    '@keyframes iwPulse{0%,80%,100%{transform:scale(.5);opacity:.3}40%{transform:scale(1);opacity:1}}',

    '#IW-bar{padding:16px 18px;border-top:1px solid #eaedf3;display:flex;gap:12px;align-items:flex-end;background:#fff;flex-shrink:0;}',
    '#IW-in{flex:1;border:1.5px solid #e2e7ef;border-radius:12px;padding:13px 16px;font-size:14px;resize:none;min-height:48px;max-height:120px;',
    '  background:var(--iris-surface,#F5F9FC);color:var(--iris-text,#1F2A37);outline:none;line-height:1.5;transition:border-color .18s,background .18s,box-shadow .18s;}',
    '#IW-in:focus{border-color:var(--iris-link,#0070AD);background:#fff;box-shadow:0 0 0 3px rgba(45,90,140,.12);}',
    '#IW-in::placeholder{color:#9aa6b6;}',
    '#IW-go{width:44px;height:44px;border-radius:12px;border:none;cursor:pointer;background:var(--iris-primary,#0070AD);color:#fff;',
    '  display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:transform .15s,opacity .15s,background .15s;}',
    '#IW-go:hover:not(:disabled){background:var(--iris-primary-strong,#005A8C);transform:translateY(-1px);}',
    '#IW-go:disabled{opacity:.4;cursor:default;}',
    '#IW-go svg{width:18px;height:18px;}',
    '#IW-ft{text-align:center;font-size:10.5px;color:#9aa6b6;padding:0 0 10px;letter-spacing:.2px;background:#fff;flex-shrink:0;}',

    '@media(max-width:640px){',
    '  #IW-panel{bottom:0;right:0;width:100vw;max-width:100vw;height:100vh;max-height:100vh;border-radius:0;border:none;}',
    '  #IW-fab{bottom:18px;right:18px;}',
    '}'
  ].join('');
  var st = document.createElement('style');
  st.textContent = CSS;
  document.head.appendChild(st);

  /* ============================ ICONES ============================ */
  var IC = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6L6 18M6 6l12 12"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>',
    linkedin: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.4c0-1.3-.02-2.95-1.8-2.95-1.8 0-2.08 1.4-2.08 2.85V21H9z"/></svg>',
    avatar: '<svg viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">' +
      '<circle cx="24" cy="24" r="24" style="fill:var(--iris-tint,#E6F4FA)"/>' +
      '<path d="M8 42v-1c0-7.2 7.2-11 16-11s16 3.8 16 11v1z" style="fill:var(--iris-primary,#0070AD)"/>' +
      '<path d="M24 9c-5.7 0-9.7 4.1-9.7 9.8 0 3.8 1.9 6.9 4.8 8.6-1.6.2-2.6 1-2.6 1h15c0-.1-1-.8-2.6-1 2.9-1.7 4.8-4.8 4.8-8.6C33.7 13.1 29.7 9 24 9z" style="fill:var(--iris-primary,#0070AD)"/>' +
      '<path d="M16.5 17.5c1.6-1 4.3-2 7.5-2s5.9 1 7.5 2c-.4-4-3.6-6.6-7.5-6.6s-7.1 2.6-7.5 6.6z" style="fill:var(--iris-primary-strong,#005A8C)"/>' +
      '<path d="M36.4 9.6l1 2.3 2.3 1-2.3 1-1 2.3-1-2.3-2.3-1 2.3-1z" style="fill:var(--iris-link,#0070AD)"/>' +
      '</svg>'
  };

  /* ============================ RENDU ============================ */
  function esc(t) { var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

  function initials(name) {
    var w = name.trim().split(/\s+/).filter(Boolean);
    if (!w.length) return '?';
    var a = w[0][0] || '';
    var b = w.length > 1 ? (w[w.length - 1][0] || '') : '';
    return (a + b).toUpperCase();
  }

  function inline(t) {
    var s = esc(t);
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
      '<a class="inl" href="$2" target="_blank" rel="noopener">$1</a>');
    return s.replace(/\n/g, '<br>');
  }

  function card(ini, title, subtitle, badges, metas, link, linkLabel) {
    var h = '<div class="IW-card"><div class="ini">' + esc(ini) + '</div><div class="body">';
    h += '<div class="nm">' + esc(title) + '</div>';
    if (subtitle) h += '<div class="rl">' + esc(subtitle) + '</div>';
    if (badges && badges.length) {
      h += '<div class="badges">';
      badges.forEach(function (b) { h += '<span class="bdg' + (b.al ? ' al' : '') + '">' + esc(b.label) + '</span>'; });
      h += '</div>';
    }
    (metas || []).forEach(function (m) { if (m) h += '<div class="meta">' + esc(m) + '</div>'; });
    if (link) h += '<a class="act" href="' + esc(link) + '" target="_blank" rel="noopener">' + IC.linkedin + esc(linkLabel || 'LinkedIn') + '</a>';
    return h + '</div></div>';
  }

  function renderContact(c) {
    var name = ((c.prenom || '') + ' ' + (c.nom || '')).trim();
    var subtitle = c.poste && c.entreprise ? (c.poste + ' chez ' + c.entreprise)
      : (c.poste || (c.entreprise ? 'chez ' + c.entreprise : ''));
    var badges = [];
    if (c.type_contact === 'alumni') badges.push({ label: 'Alumni', al: true });
    else if (c.type_contact === 'client_actuel') badges.push({ label: 'Client actuel' });
    var metas = [];
    var coords = [c.telephone, c.email].filter(Boolean).join('  ·  ');
    if (c.localisation) metas.push(c.localisation);
    if (coords) metas.push(coords);
    if (c.amene_par) metas.push('Amené par ' + String(c.amene_par).replace(/\s+/g, ' ').trim());
    return card(initials(name), name, subtitle, badges, metas, c.linkedin, 'LinkedIn');
  }

  function renderHunter(h) {
    var title = h.cabinet || h.contact_principal || 'Cabinet';
    var subtitle = (h.cabinet && h.contact_principal) ? h.contact_principal : '';
    var metas = [];
    var spec = (h.specialites || []).filter(Boolean);
    var sect = (h.secteurs || []).filter(Boolean);
    if (spec.length) metas.push('Spécialités : ' + spec.join(', '));
    if (sect.length) metas.push('Secteurs : ' + sect.join(', '));
    var contact = [h.email, h.telephone].filter(Boolean).join(' | ');
    if (contact) metas.push(contact);
    return card(initials(title), title, subtitle, [], metas, '', '');
  }

  function renderMessage(text) {
    return (text || '').split(/\n{2,}/).map(function (p) { p = p.trim(); return p ? '<p>' + inline(p) + '</p>' : ''; }).join('');
  }

  function renderReply(d) {
    var html = renderMessage(d.response);
    (d.contacts || []).forEach(function (c) { html += renderContact(c); });
    (d.hunters || []).forEach(function (h) { html += renderHunter(h); });
    return html;
  }

  /* ============================ HTML ============================ */
  var root = document.createElement('div');
  root.id = 'IW';
  root.innerHTML =
    '<button id="IW-fab"><span class="fav">' + IC.avatar + '</span><span>Iris</span></button>' +
    '<div id="IW-panel">' +
    '  <div id="IW-head">' +
    '    <div class="av">' + IC.avatar + '</div>' +
    '    <div class="info"><b>Iris</b><span><i id="IW-dot"></i>Assistante du réseau</span></div>' +
    '    <button id="IW-x" aria-label="Fermer">' + IC.close + '</button>' +
    '  </div>' +
    '  <div id="IW-chat"></div>' +
    '  <div id="IW-bar">' +
    '    <textarea id="IW-in" placeholder="Rechercher un contact…" rows="1"></textarea>' +
    '    <button id="IW-go" aria-label="Envoyer">' + IC.send + '</button>' +
    '  </div>' +
    '  <div id="IW-ft">Iris &middot; Cabinet Astrolabe</div>' +
    '</div>';

  /* ============================ INIT ============================ */
  function init() {
    document.body.appendChild(root);
    var fab = document.getElementById('IW-fab');
    var panel = document.getElementById('IW-panel');
    var chat = document.getElementById('IW-chat');
    var inp = document.getElementById('IW-in');
    var go = document.getElementById('IW-go');
    var dot = document.getElementById('IW-dot');

    function show() { open = true; panel.classList.add('show'); fab.classList.add('hide'); setTimeout(function () { inp.focus(); }, 220); }
    function hide() { open = false; panel.classList.remove('show'); fab.classList.remove('hide'); }
    fab.onclick = function () { open ? hide() : show(); };
    document.getElementById('IW-x').onclick = hide;
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && open) hide(); });

    function add(role, html) {
      var d = document.createElement('div');
      d.className = 'IW-m ' + role;
      d.innerHTML = '<div class="IW-b">' + html + '</div>';
      chat.appendChild(d);
      chat.scrollTop = chat.scrollHeight;
      return d;
    }

    add('a', renderMessage(
      'Bonjour, je suis **Iris**, l’assistante du Cabinet Astrolabe.\n\n' +
      'Je vous aide à identifier des contacts dirigeants et des chasseurs de tête dans le réseau.'
    ));
    var chips = document.createElement('div');
    chips.className = 'IW-m a';
    chips.innerHTML = '<div class="IW-b"><div id="IW-chips">' +
      ['une DRH chez Sanofi', 'un dirigeant dans l’énergie', 'un cabinet de chasseurs de tête']
        .map(function (q) { return '<button>' + esc(q) + '</button>'; }).join('') +
      '</div></div>';
    chat.appendChild(chips);
    chips.querySelectorAll('button').forEach(function (b) {
      b.onclick = function () { inp.value = b.textContent; send(); };
    });

    fetch(API_URL + '/api/health').then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.status === 'ok') dot.classList.add('ok'); }).catch(function () {});

    go.onclick = send;
    inp.onkeydown = function (e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };
    inp.oninput = function () { this.style.height = 'auto'; this.style.height = Math.min(this.scrollHeight, 110) + 'px'; };

    function send() {
      var t = inp.value.trim();
      if (!t || loading) return;
      add('u', '<p>' + esc(t) + '</p>');
      inp.value = ''; inp.style.height = 'auto';
      loading = true; go.disabled = true;

      var typing = add('a', '<div class="IW-dots"><i></i><i></i><i></i></div>');

      fetch(API_URL + '/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: t, history: history, exclude_ids: shownIds })
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          typing.remove();
          if (!d.success) throw new Error(d.error || 'échec');
          add('a', renderReply(d));
          (d.contacts || []).forEach(function (c) { if (c.id && shownIds.indexOf(c.id) < 0) shownIds.push(c.id); });
          history.push({ role: 'user', content: t }, { role: 'assistant', content: d.response });
          if (history.length > 20) history = history.slice(-20);
        })
        .catch(function () {
          typing.remove();
          add('a', '<p>Désolée, une erreur est survenue. Pouvez-vous reformuler votre demande ?</p>');
        })
        .finally(function () { loading = false; go.disabled = false; inp.focus(); });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
