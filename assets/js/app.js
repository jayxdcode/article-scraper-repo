(() => {
  const DEFAULTS = {
    layout: 'sidebar',
    compact: false,
    expanded: false,
    themeMode: 'system',
    preset: 'discord-dark',
    accent: '#44ccff',
    font: 'system',
    fontSize: 14,
    reduceMotion: false,
    highContrast: false,
    largeText: false,
  };
  const LS_KEY = 'jx.catalog.settings';
  const app = document.getElementById('app');
  const projectGrid = document.getElementById('projectGrid');
  const pageTitle = document.getElementById('pageTitle');
  const footerLayout = document.getElementById('footerLayout');

  const FEEDS = [
    {
      id: 'inquirer',
      source: 'Inquirer (Opinion)',
      tagline: 'Opinion / Editorials — opinion.inquirer.net',
      category: 'opinion',
      cmd: 'node node/inquirer/scrape-inquirer.js --discover'
    },
    {
      id: 'philstar',
      source: 'Philstar',
      tagline: 'Opinion / News — philstar.com',
      category: 'opinion',
      cmd: 'node node/philstar/scrape-philstar.js --discover'
    }
  ];

  function loadSettings(){
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return {...DEFAULTS};
      return Object.assign({}, DEFAULTS, JSON.parse(raw));
    } catch(e) { return {...DEFAULTS}; }
  }
  function saveSettings(s){ localStorage.setItem(LS_KEY, JSON.stringify(s)); applySettings(s); }
  function applySettings(s){
    app.classList.remove('layout-sidebar','layout-topbar','layout-bottombar','compact','expanded');
    if (s.layout === 'sidebar') app.classList.add('layout-sidebar');
    if (s.layout === 'topbar') app.classList.add('layout-topbar');
    if (s.layout === 'bottombar') app.classList.add('layout-bottombar');
    if (s.compact) app.classList.add('compact'); else app.classList.remove('compact');
    if (s.expanded) app.classList.add('expanded'); else app.classList.remove('expanded');
    document.documentElement.style.setProperty('--accent', s.accent || DEFAULTS.accent);
    document.documentElement.style.setProperty('--font-size', s.fontSize + 'px');
    if (s.themeMode === 'light') document.documentElement.setAttribute('data-theme','light');
    else if (s.themeMode === 'dark') document.documentElement.setAttribute('data-theme','dark');
    else {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    }
    if (s.largeText) document.body.style.fontSize = (s.fontSize + 2) + 'px'; else document.body.style.fontSize = s.fontSize + 'px';
    document.documentElement.setAttribute('data-reduce-motion', s.reduceMotion ? 'true' : 'false');
    document.documentElement.setAttribute('data-high-contrast', s.highContrast ? 'true' : 'false');
    footerLayout.textContent = s.layout || 'side';
  }

  function renderFeeds(){
    projectGrid.innerHTML = '';
    FEEDS.forEach(feed => {
      const card = document.createElement('div');
      card.className = 'news-card card';
      const thumbUrl = `assets/images/${feed.id}.webp`;
      card.innerHTML = `
        <img class="news-thumb" src="${thumbUrl}" alt="" onerror="this.style.display='none'">
        <div class="news-body">
          <div class="news-meta"><div class="pill-source">${feed.source}</div><div style="margin-left:auto;color:var(--muted)" id="meta-${feed.id}">—</div></div>
          <h3 class="news-title" id="title-${feed.id}">${feed.tagline}</h3>
          <div class="news-excerpt" id="excerpt-${feed.id}">Latest articles discovered by the scraper will appear here after a run. Use Run to trigger a new fetch.</div>
          <div class="news-actions">
            <button class="btn ghost run-btn" data-id="${feed.id}"><i class='bx bx-refresh'></i> Run</button>
            <button class="btn" data-id="${feed.id}" id="cmd-${feed.id}"><i class='bx bx-copy'></i> Cmd</button>
            <a class="btn ghost" href="#" target="_blank" id="open-${feed.id}">Open</a>
          </div>
        </div>
      `;
      projectGrid.appendChild(card);
    });
  }

  function wireUI(settings){
    document.querySelectorAll('.nav-btn').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        const view = btn.getAttribute('data-view');
        document.querySelectorAll('.view').forEach(el=>el.classList.add('hidden'));
        const sel = document.querySelector(`.view[data-view="${view}"]`);
        if (sel) sel.classList.remove('hidden');
        pageTitle.textContent = view.charAt(0).toUpperCase() + view.slice(1);
      });
    });

    projectGrid.addEventListener('click', e=>{
      const run = e.target.closest('.run-btn');
      if (run) {
        const id = run.getAttribute('data-id');
        const feed = FEEDS.find(f=>f.id===id);
        alert(`Trigger scraper for ${feed.source}\nCommand: ${feed.cmd}\n\nWire this to CI/webhook to run automatically.`);
      }
      const cmdBtn = e.target.closest('button[id^="cmd-"]');
      if (cmdBtn) {
        const id = cmdBtn.id.replace('cmd-','');
        const feed = FEEDS.find(f=>f.id===id);
        navigator.clipboard?.writeText(feed.cmd).then(()=> alert('Command copied to clipboard'), ()=> alert('Command: ' + feed.cmd));
      }
      const open = e.target.closest('a[id^="open-"]');
      if (open) {
        const id = open.id.replace('open-','');
        const config = window.jxCatalog && window.jxCatalog.config;
        let url = '#';
        if (config && config.sites && config.sites[id] && config.sites[id].index_url) url = config.sites[id].index_url;
        window.open(url, '_blank');
      }
    });

    document.getElementById('runAll').addEventListener('click', ()=>{
      alert('Run all scrapers: trigger your CI workflows or run the listed commands locally.');
    });

    // settings wiring
    document.querySelectorAll('input[name="layoutMode"]').forEach(r=>{
      r.checked = settings.layout === r.value;
      r.addEventListener('change', ()=>{ settings.layout = r.value; saveSettings(settings); });
    });
    const compactToggle = document.getElementById('compactToggle');
    if (compactToggle) { compactToggle.checked = settings.compact; compactToggle.addEventListener('change', e=>{ settings.compact = e.target.checked; saveSettings(settings); }); }
    const expandedToggle = document.getElementById('expandedToggle');
    if (expandedToggle) { expandedToggle.checked = settings.expanded; expandedToggle.addEventListener('change', e=>{ settings.expanded = e.target.checked; saveSettings(settings); }); }

    const themeMode = document.getElementById('themeMode');
    if (themeMode) { themeMode.value = settings.themeMode; themeMode.addEventListener('change', e=>{ settings.themeMode = e.target.value; saveSettings(settings); }); }

    const preset = document.getElementById('themePreset');
    if (preset) { preset.value = settings.preset || 'discord-dark'; preset.addEventListener('change', e=>{ settings.preset = e.target.value; applyPreset(settings.preset, settings); saveSettings(settings); }); }

    const accent = document.getElementById('accentPicker');
    if (accent) { accent.value = settings.accent || '#44ccff'; accent.addEventListener('input', e=>{ settings.accent = e.target.value; saveSettings(settings); }); }

    const fontSel = document.getElementById('fontSelect');
    if (fontSel) { fontSel.value = settings.font; fontSel.addEventListener('change', e=>{ settings.font = e.target.value; saveSettings(settings); }); }

    const fontSize = document.getElementById('fontSize');
    if (fontSize) { fontSize.value = settings.fontSize; fontSize.addEventListener('input', e=>{ settings.fontSize = parseInt(e.target.value,10); saveSettings(settings); }); }

    const reduceMotion = document.getElementById('reduceMotion');
    if (reduceMotion) { reduceMotion.checked = settings.reduceMotion; reduceMotion.addEventListener('change', e=>{ settings.reduceMotion = e.target.checked; saveSettings(settings); }); }
    const highContrast = document.getElementById('highContrast');
    if (highContrast) { highContrast.checked = settings.highContrast; highContrast.addEventListener('change', e=>{ settings.highContrast = e.target.checked; saveSettings(settings); }); }
    const largeText = document.getElementById('largeText');
    if (largeText) { largeText.checked = settings.largeText; largeText.addEventListener('change', e=>{ settings.largeText = e.target.checked; saveSettings(settings); }); }

    const exportBtn = document.getElementById('exportSettings');
    if (exportBtn) exportBtn.addEventListener('click', ()=> { const blob = new Blob([JSON.stringify(settings,null,2)],{type:'application/json'}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download='catalog-settings.json'; a.click(); a.remove(); });

    const importBtn = document.getElementById('importSettings');
    if (importBtn) importBtn.addEventListener('click', ()=> document.getElementById('importFile').click());

    const importFile = document.getElementById('importFile');
    if (importFile) importFile.addEventListener('change', e=>{
      const f = e.target.files[0];
      if (!f) return;
      const reader = new FileReader();
      reader.onload = () => {
        try { const obj = JSON.parse(reader.result); Object.assign(settings, obj); saveSettings(settings); location.reload(); } catch(err){ alert('Invalid JSON'); }
      };
      reader.readAsText(f);
    });

    const openSettings = document.getElementById('openSettings');
    if (openSettings) openSettings.addEventListener('click', ()=> {
      document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
      const sbtn = document.querySelector('.nav-btn[data-view="settings"]');
      if (sbtn) sbtn.classList.add('active');
      document.querySelectorAll('.view').forEach(el=>el.classList.add('hidden'));
      const sel = document.querySelector('.view-settings');
      if (sel) sel.classList.remove('hidden');
    });
  }

  function applyPreset(preset, settings){
    const map = {
      'discord-dark': {accent:'#5865F2'},
      'discord-light': {accent:'#5865F2'},
      'midnight': {accent:'#7b61ff'},
      'solarized': {accent:'#b58900'},
      'aurora': {accent:'#9b59ff'},
      'matrix': {accent:'#1abc9c'}
    };
    const presetObj = map[preset] || map['discord-dark'];
    if (presetObj.accent) settings.accent = presetObj.accent;
  }

  async function loadRepoConfig(){
    try {
      const resp = await fetch('config.json', {cache:'no-store'});
      if (!resp.ok) return null;
      const obj = await resp.json();
      window.jxCatalog = Object.assign(window.jxCatalog || {}, { config: obj });
      return obj;
    } catch(e){ return null; }
  }

  (async () => {
    const settings = loadSettings();
    applyPreset(settings.preset, settings);
    applySettings(settings);
    renderFeeds();
    wireUI(settings);
    await loadRepoConfig();
    window.jxCatalog = window.jxCatalog || {};
    window.jxCatalog.settings = settings;
    window.jxCatalog.saveSettings = saveSettings;
    console.log('News catalog ready');
  })();

})();