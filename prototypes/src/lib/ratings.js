// Manager ratings: each attribute scored against the other five (best = 95, worst = 60), overall = average.
// JSNRatings.compute(D) returns the scores; JSNRatings.mount(root, D) renders the cards and a profile.
window.JSNRatings = (() => {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const sign = n => (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(Math.round(n));
  const NAMES = ['Jim','Ash','Haz','Cal','Dez','Gear'];
  const ordinal = k => k + (['th','st','nd','rd'][(k % 100 - 20) % 10] || ['th','st','nd','rd'][k % 100] || 'th');

  function compute(D) {
    const M = Object.fromEntries(D.table.map(r => [r.manager, r]));
    const ATTR = [
      {k: 'CAP', name: 'Captaincy', style: 'Armband specialist', raw: n => M[n].metrics.cap_pts, say: v => `${Math.round(v)} points from the armband`},
      {k: 'SCT', name: 'Scouting', style: 'Scout', raw: n => M[n].metrics.diff_global, say: v => `${Math.round(v)} points from players under 10% owned`},
      {k: 'MKT', name: 'Transfers', style: 'Wheeler-dealer', raw: n => D.transfers[n].normal_net, say: v => `${sign(v)} net from transfers`},
      {k: 'SEL', name: 'Selection', style: 'Selector', raw: n => -M[n].metrics.bench, say: v => `${Math.round(-v)} points left on the bench`},
      {k: 'CON', name: 'Consistency', style: 'Metronome', raw: n => -M[n].metrics.spread, say: v => `${(-v).toFixed(1)} point weekly spread`},
      {k: 'LUK', name: 'Luck', style: 'Chancer', raw: n => D.luck[n].vs_group, say: v => `${sign(v)} against the group's luck`},
    ];
    const R = {};
    NAMES.forEach(n => R[n] = {attrs: {}});
    ATTR.forEach(a => { const vals = NAMES.map(a.raw), lo = Math.min(...vals), hi = Math.max(...vals);
      NAMES.forEach(n => { const v = a.raw(n); R[n].attrs[a.k] = {score: hi === lo ? 78 : Math.round(60 + 35 * (v - lo) / (hi - lo)), raw: v}; }); });
    NAMES.forEach(n => { const s = ATTR.map(a => R[n].attrs[a.k].score);
      R[n].ovr = Math.round(s.reduce((x, y) => x + y, 0) / s.length);
      R[n].style = ATTR.reduce((b, a) => R[n].attrs[a.k].score > R[n].attrs[b.k].score ? a : b).style; });
    return {M, ATTR, R};
  }

  function rivals(D, n) {
    let worst = null, best = null;
    NAMES.filter(o => o !== n).forEach(o => { const p = D.h2h[`${n}-${o}`] || D.h2h[`${o}-${n}`], d = p.wins[o] - p.wins[n];
      if (!worst || d > worst.d) worst = {o, d, me: p.wins[n], them: p.wins[o]};
      if (!best || d < best.d) best = {o, d, me: p.wins[n], them: p.wins[o]}; });
    return {worst, best};
  }

  function mount(root, D) {
    const {M, ATTR, R} = compute(D);
    const order = [...NAMES].sort((a, b) => R[b].ovr - R[a].ovr);
    root.classList.add('ratings');
    root.innerHTML = `<div class="rt-deck">${order.map(n => `<button class="rt-card" style="--c:var(--${n})" data-n="${n}" aria-pressed="false" aria-label="${n}, rated ${R[n].ovr}"><span class="rt-ovr cd">${R[n].ovr}</span><span class="rt-sty">${R[n].style}</span><span class="rt-nm cd">${n}</span><span class="rt-tm">${esc(M[n].team)}</span><span class="rt-at">${ATTR.map(a => `<span><b>${R[n].attrs[a.k].score}</b>${a.k}</span>`).join('')}</span></button>`).join('')}</div>
      <section class="rt-profile" aria-live="polite"></section>
      <p class="rt-how">Each attribute is scored against the other five, so 95 is the best in the group and 60 the worst. The overall is the average of the six, and the playing style is your best attribute. Ratings reward decisions, not points: the league leader doesn't have to be top rated.</p>`;
    const prof = root.querySelector('.rt-profile');

    function show(n) {
      root.querySelectorAll('.rt-card').forEach(b => b.setAttribute('aria-pressed', b.dataset.n === n));
      const r = R[n], gws = Object.entries(D.weeks[n]);
      const best = gws.reduce((a, b) => b[1].points > a[1].points ? b : a), worst = gws.reduce((a, b) => b[1].points < a[1].points ? b : a);
      const rv = rivals(D, n), held = D.awards.filter(a => a.winners.includes(n)).map(a => a.title);
      prof.style.setProperty('--c', `var(--${n})`);
      prof.innerHTML = `<div class="rt-side"><div class="rt-ovr cd">${r.ovr}</div><div class="rt-nm cd">${n}</div><p>${esc(M[n].team)}</p><p>${ordinal(M[n].rank)} in the group on ${M[n].points} points.</p><span class="rt-styl">Plays as: ${r.style}</span></div>
      <div class="rt-body">
        <div><h3>Attributes</h3>${ATTR.map(a => `<div class="rt-attr"><span>${a.name}</span><b>${r.attrs[a.k].score}</b><span class="rt-bar"><i style="width:${(r.attrs[a.k].score - 50) * 2}%;background:var(--${n})"></i></span><small>${a.say(r.attrs[a.k].raw)}</small></div>`).join('')}</div>
        <div class="rt-facts">
          <div class="rt-fact"><span>Best week</span><b>${best[1].points}</b><em>Gameweek ${best[0]}, ${esc(best[1].star)} ${best[1].star_pts}</em></div>
          <div class="rt-fact"><span>Worst week</span><b>${worst[1].points}</b><em>Gameweek ${worst[0]}</em></div>
          <div class="rt-fact"><span>Nemesis</span><b style="color:var(--${rv.worst.o})">${rv.worst.d > 0 ? rv.worst.o : 'None yet'}</b><em>${rv.worst.d > 0 ? `Beats ${n} ${rv.worst.them} weeks to ${rv.worst.me}` : `Nobody beats ${n} more often than not`}</em></div>
          <div class="rt-fact"><span>Owns</span><b style="color:var(--${rv.best.o})">${rv.best.d < 0 ? rv.best.o : 'Nobody'}</b><em>${rv.best.d < 0 ? `${n} wins ${rv.best.me} weeks to ${rv.best.them}` : 'No clear victim yet'}</em></div>
        </div>
        <div><h3>Signature players</h3><ul class="rt-sig">${D.signature[n].map(s => `<li><span>${esc(s.player)}</span><b>${s.pts}</b></li>`).join('')}</ul></div>
        <div><h3>Trophy cabinet</h3><div class="rt-badges">${held.length ? held.map(t => `<span>${esc(t)}</span>`).join('') : '<span style="border-style:dashed;color:var(--muted)">Empty, for now</span>'}</div></div>
      </div>`;
    }
    root.querySelector('.rt-deck').addEventListener('click', e => { const b = e.target.closest('.rt-card'); if (!b) return;
      show(b.dataset.n);
      prof.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth', block: 'start'}); });
    show(order[0]);
  }

  return {compute, mount};
})();
