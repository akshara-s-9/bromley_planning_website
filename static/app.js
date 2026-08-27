const BROMLEY_CENTRE = [51.3800, 0.0200];
const BROMLEY_REGISTER = 'https://planningaccess.bromley.gov.uk/pr/s/';

const els = {
  from: document.getElementById('from'),
  to: document.getElementById('to'),
  includeAll: document.getElementById('include-all'),
  apply: document.getElementById('apply'),
  results: document.getElementById('results'),
  summary: document.getElementById('summary'),
  statusLine: document.getElementById('status-line'),
};

const map = L.map('map').setView(BROMLEY_CENTRE, 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors',
}).addTo(map);

const markerLayer = L.layerGroup().addTo(map);
const markersByUid = new Map();

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function formatDate(iso) {
  if (!iso) return 'no decision date';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

// navigator.clipboard is unavailable outside a secure context, so serving this
// on a plain-HTTP LAN address falls back to the old execCommand path.
async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      /* fall through */
    }
  }

  const scratch = document.createElement('textarea');
  scratch.value = text;
  scratch.setAttribute('readonly', '');
  scratch.style.position = 'fixed';
  scratch.style.opacity = '0';
  document.body.appendChild(scratch);
  scratch.select();

  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  document.body.removeChild(scratch);
  return ok;
}

function selectCard(uid) {
  els.results.querySelectorAll('li').forEach((li) => {
    li.classList.toggle('active', li.dataset.uid === uid);
  });
  const card = els.results.querySelector(`li[data-uid="${CSS.escape(uid)}"]`);
  if (card) card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function buildCard(row) {
  const li = document.createElement('li');
  li.dataset.uid = row.uid;

  // Bromley's own register has no working deep link -- its Salesforce record
  // URLs render "Invalid Page" -- so the reference has to be searched for.
  // PlanIt's record page is the one link that reliably resolves.
  const links = [];
  if (row.planit_url) {
    links.push(`<a href="${row.planit_url}" target="_blank" rel="noopener">Full record &amp; documents &rarr;</a>`);
  }
  links.push(`<a href="${BROMLEY_REGISTER}" target="_blank" rel="noopener">Search Bromley register &rarr;</a>`);
  links.push(`<button class="copy-ref" type="button" data-ref="${row.uid}">Copy ref</button>`);

  li.innerHTML = `
    <div class="addr">${row.address || 'Address not recorded'}</div>
    <div class="meta">
      <span class="pc">${row.postcode || 'no postcode'}</span>
      <span>Approved ${formatDate(row.decided_date)}</span>
      <span>Ref ${row.uid}</span>
    </div>
    <p class="desc">${row.description || ''}</p>
    <div class="links">${links.join('')}</div>
    ${row.classification_reason ? `<div class="reason">Matched: ${row.classification_reason}</div>` : ''}
  `;

  li.addEventListener('click', (event) => {
    if (event.target.tagName === 'A') return;

    if (event.target.classList.contains('copy-ref')) {
      const button = event.target;
      copyText(button.dataset.ref).then((ok) => {
        button.textContent = ok ? 'Copied' : button.dataset.ref;
        setTimeout(() => { button.textContent = 'Copy ref'; }, 1800);
      });
      return;
    }

    selectCard(row.uid);
    const marker = markersByUid.get(row.uid);
    if (marker) {
      map.setView(marker.getLatLng(), 16);
      marker.openPopup();
    }
  });

  return li;
}

function render(rows) {
  els.results.innerHTML = '';
  markerLayer.clearLayers();
  markersByUid.clear();

  if (!rows.length) {
    els.results.innerHTML = '<li class="empty">No approvals found for this date range. Try widening the dates, or run a refresh to pull newer decisions.</li>';
    els.summary.textContent = '0 approvals';
    return;
  }

  const withLocation = [];

  rows.forEach((row) => {
    els.results.appendChild(buildCard(row));

    if (row.latitude == null || row.longitude == null) return;

    const marker = L.marker([row.latitude, row.longitude]).bindPopup(
      `<strong>${row.address || row.uid}</strong><br>${row.postcode || ''}<br>` +
      `Approved ${formatDate(row.decided_date)}` +
      (row.planit_url ? `<br><a href="${row.planit_url}" target="_blank" rel="noopener">Full record</a>` : '')
    );
    marker.on('click', () => selectCard(row.uid));
    marker.addTo(markerLayer);
    markersByUid.set(row.uid, marker);
    withLocation.push([row.latitude, row.longitude]);
  });

  const mapped = withLocation.length;
  els.summary.textContent =
    `${rows.length} approval${rows.length === 1 ? '' : 's'}` +
    (mapped < rows.length ? ` — ${mapped} mapped, ${rows.length - mapped} without coordinates` : '');

  if (withLocation.length) {
    map.fitBounds(L.latLngBounds(withLocation), { padding: [40, 40], maxZoom: 15 });
  }
}

async function loadStatus() {
  try {
    const status = await (await fetch('/api/status')).json();
    const last = status.last_refresh;
    els.statusLine.textContent = last
      ? `Cache: ${status.new_build} new-build of ${status.total_permitted} permissions; last refreshed ${last.ran_at.replace('T', ' ')}Z`
      : 'Cache is empty — run: python -m app.refresh';
  } catch {
    els.statusLine.textContent = 'Status unavailable';
  }
}

async function load() {
  els.summary.textContent = 'Loading…';
  const params = new URLSearchParams();
  if (els.from.value) params.set('decided_from', els.from.value);
  if (els.to.value) params.set('decided_to', els.to.value);
  if (els.includeAll.checked) params.set('include_all', 'true');

  try {
    const rows = await (await fetch(`/api/applications?${params}`)).json();
    render(rows);
  } catch (err) {
    els.summary.textContent = `Could not load applications: ${err.message}`;
  }
}

els.apply.addEventListener('click', load);
els.from.value = isoDaysAgo(365);
els.to.value = isoDaysAgo(0);

loadStatus();
load();
