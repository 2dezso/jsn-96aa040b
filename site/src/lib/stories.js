// Gameweek stories: shared by the standalone page and the This week tab.
// JSNStories.build(D) returns the slides; JSNStories.mount(root, D, opts) renders a player into root.
window.JSNStories = (() => {
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const sign = n => (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(Math.round(n));
  const NAMES = ['Jim','Ash','Haz','Cal','Dez','Jack'];
  const list = a => a.length < 3 ? a.join(' and ') : a.slice(0, -1).join(', ') + ' and ' + a.slice(-1);
  const C = n => `var(--${n})`;

  function build(D) {
    const GW = D.meta.latest_gw, W = NAMES.map(n => ({n, ...D.weeks[n][GW]})), gw = D.gw_winners[GW];
    const S = [];
    const slide = (bg, inner, light) => S.push({bg, light, inner});

    slide('var(--pitch)', `<h1>Gameweek ${GW}, as told by JSN</h1><p>The week, the luck, the bad calls. Where things are wrong.</p><div class="st-spacer"></div><div class="st-pills">${NAMES.map(n => `<span style="background:${C(n)}">${n}</span>`).join('')}</div>`);

    const champ = W.filter(w => gw.winners.includes(w.n))[0];
    slide(C(champ.n), `<h1>${list(gw.winners)} ${gw.winners.length > 1 ? 'share' : 'wins'} the week</h1><p>${esc(champ.star)} did the heavy lifting with ${champ.star_pts}.${champ.hits ? ` Even after a −${champ.hits} hit.` : ''}</p><div class="st-num">${gw.top}</div>`);

    const low = W.filter(w => gw.spoon.includes(w.n))[0];
    slide('#FFFFFF', `<h1 style="color:${C(low.n)}">Wooden spoon: ${list(gw.spoon)}</h1><p>${low.bench_pts >= 8 ? `With ${low.bench_pts} sat on the bench. Pick the right XI next time.` : `Captain ${esc(low.captain)} returned ${low.captain_pts}.`}</p><div class="st-num" style="color:${C(low.n)}">${gw.low}</div>`, true);

    const caps = {};
    W.forEach(w => { (caps[w.captain] ||= {pts: w.captain_pts, who: []}).who.push(w.n); });
    const cl = Object.entries(caps).sort((a, b) => b[1].pts - a[1].pts);
    const crowd = [...cl].sort((a, b) => b[1].who.length - a[1].who.length)[0];
    slide('#FFFFFF', `<h1>${crowd[1].who.length === 6 ? 'All six of you' : `${crowd[1].who.length} of you`} captained ${esc(crowd[0])}</h1><p>${cl.length > 1 ? (cl[0][0] === crowd[0] ? 'The crowd got it right.' : `${list(cl[0][1].who)} went ${esc(cl[0][0])} and won the armband by ${cl[0][1].pts - crowd[1].pts}.`) : 'Not one of you dared to be different.'}</p><div class="st-split">${cl.slice(0, 2).map(([p, c]) => `<div><div class="st-p">${c.pts}</div><div class="st-n">${esc(p)}</div><div class="st-pills" style="margin-top:6px">${c.who.map(n => `<span style="background:${C(n)};color:#fff">${n}</span>`).join('')}</div></div>`).join('')}</div>`, true);

    const bench = [...W].sort((a, b) => b.bench_pts - a.bench_pts)[0];
    slide(C(bench.n), `<h1>${bench.n} left ${bench.bench_pts} on the bench</h1><p>Most in the group this week. ${bench.bench_pts > 10 ? 'That would have changed the week.' : ''}</p><div class="st-num">${bench.bench_pts}</div>`);

    const groups = {};
    D.jsn.filter(i => i.severity !== 'info').forEach(i => { const k = i.player + i.text; (groups[k] ||= {...i, who: []}).who.push(i.manager); });
    const big = Object.values(groups).sort((a, b) => b.who.length - a.who.length)[0];
    if (big) slide('var(--out)', `<h1>${big.who.length === 6 ? 'All six of you' : `${big.who.length} of you`} own ${esc(big.player)}</h1><p>${esc(big.text)}. Gameweek ${D.meta.next_gw} deadline is coming.</p><div class="st-spacer"></div><div class="st-pills">${big.who.map(n => `<span>${n}</span>`).join('')}</div>`);

    const L = Object.entries(D.luck).map(([n, x]) => ({n, v: x.vs_group})).sort((a, b) => b.v - a.v), lm = Math.max(...L.map(x => Math.abs(x.v)));
    slide(C(L[0].n), `<h1>${L[0].n} is ${Math.round(L[0].v)} points luckier than the group</h1><p>Points beyond what the chances deserved, season so far.</p><div class="st-spacer"></div>${L.map(x => `<div class="st-lb"><span>${x.n}</span><span class="st-t"><i style="${x.v >= 0 ? 'left:50%' : 'right:50%'};width:${Math.abs(x.v) / lm * 50}%"></i></span><span style="text-align:right">${sign(x.v)}</span></div>`).join('')}`);

    const tw = Object.entries(D.transfers).filter(([, v]) => v.worst).map(([n, v]) => ({n, ...v.worst})).sort((a, b) => a.net - b.net)[0];
    if (tw) slide(C(tw.n), `<h1>${tw.n} sold ${esc(tw.out)} to buy ${esc(tw.in)}</h1><p>${esc(tw.out)} has scored ${tw.pts_out} since. ${esc(tw.in)} has ${tw.pts_in}. Worst transfer in the group.</p><div class="st-num">${sign(tw.net)}</div>`);

    const T = D.table, pos = [[180, 62], [100, 180], [260, 180], [100, 298], [260, 298], [180, 408]];
    let svg = '<rect width="360" height="500" rx="10" fill="#0E8A52"/><g fill="none" stroke="#fff" stroke-width="2" opacity=".7"><rect x="14" y="14" width="332" height="472"/><line x1="14" y1="250" x2="346" y2="250"/><circle cx="180" cy="250" r="42"/><rect x="95" y="14" width="170" height="62"/><rect x="95" y="424" width="170" height="62"/></g>';
    svg += T.map((r, i) => { const [x, y] = pos[i]; return `<circle cx="${x}" cy="${y}" r="27" fill="${C(r.manager)}" stroke="#fff" stroke-width="${i ? 2 : 4}"/><text x="${x}" y="${y + 9}" text-anchor="middle" font-size="26" font-weight="700" fill="#fff">${r.rank}</text><text x="${x}" y="${y + 47}" text-anchor="middle" font-size="15" font-weight="700" fill="#fff">${r.manager} ${r.points}</text>`; }).join('');
    slide('var(--pitch)', `<h1>${T[0].manager} up front. ${T[T.length - 1].manager} in goal.</h1><svg class="st-pitch" viewBox="0 0 360 500" role="img" aria-label="League table as a formation">${svg}</svg>`);

    const mil = D.awards.find(a => a.key === 'milner');
    slide('#FFFFFF', `<h1 style="color:${C(mil.winner)}">The Milner Award goes to ${mil.winner}</h1><p>No hits. No drama. A ${mil.value.toFixed(1)} point weekly spread. Top of the table anyway.</p><div class="st-num" style="color:${C(mil.winner)}">${T.find(r => r.manager === mil.winner).points}</div>`, true);
    return S;
  }

  function mount(root, D, opts = {}) {
    const S = build(D), GW = D.meta.latest_gw;
    let i = Math.min(S.length - 1, Math.max(0, (opts.start || 1) - 1));
    root.classList.add('stories');
    // opts.autoplay = ms per slide; loops, pauses on hover, when hidden, or with the Pause button. Slides swap
    // without animating, so it runs under reduced motion too.
    const dur = opts.autoplay || 0, canPlay = dur > 0;
    let playing = canPlay, hover = false, elapsed = 0, last = null;
    root.innerHTML = `<div class="st-stage"><div class="st-bars" aria-hidden="true">${S.map(() => '<i><b></b></i>').join('')}</div><div class="st-slot" aria-live="${canPlay ? 'off' : 'polite'}"></div><div class="st-nav"><button class="st-prev">Previous</button><span class="st-count"></span>${canPlay ? '<button class="st-play">Pause</button>' : ''}<button class="st-next">Next</button></div></div>`;
    const q = s => root.querySelector(s), fills = [...root.querySelectorAll('.st-bars b')];
    function render() {
      const s = S[i];
      q('.st-slot').innerHTML = `<div class="st-slide${s.light ? ' st-light' : ''}" style="--bg:${s.bg}" role="group" aria-roledescription="slide" aria-label="${i + 1} of ${S.length}">${s.inner}<div class="st-foot"><b>JSN</b><span>Jim Sport News, gameweek ${GW}</span></div><span class="st-zone"></span></div>`;
      elapsed = 0;
      fills.forEach((b, k) => { b.style.transform = `scaleX(${k < i ? 1 : 0})`; });
      q('.st-count').textContent = `${i + 1} of ${S.length}`;
      q('.st-prev').disabled = i === 0;
      q('.st-next').disabled = i === S.length - 1 && !playing;
      if (opts.onChange) opts.onChange(i + 1);
    }
    const go = d => { i = Math.min(S.length - 1, Math.max(0, i + d)); render(); };
    if (canPlay) {
      const active = () => !document.hidden && !hover && (!opts.isActive || opts.isActive());
      // a plain timer, not animation frames: those get throttled or stopped in some browsers
      setInterval(() => {
        const t = performance.now();
        if (playing && active()) {
          if (last !== null) elapsed += t - last;
          last = t;
          if (elapsed >= dur) { i = (i + 1) % S.length; render(); }
          fills[i].style.transform = `scaleX(${Math.min(1, elapsed / dur)})`;
        } else last = null;
      }, 100);
      q('.st-slot').addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') hover = true; });
      q('.st-slot').addEventListener('pointerleave', () => { hover = false; });
      q('.st-play').addEventListener('click', e => { playing = !playing; e.target.textContent = playing ? 'Pause' : 'Play'; q('.st-next').disabled = i === S.length - 1 && !playing; });
    }
    const next = () => (playing && i === S.length - 1 ? (i = 0, render()) : go(1));
    q('.st-slot').addEventListener('click', e => (e.target.closest('.st-zone') ? go(-1) : next()));
    q('.st-prev').addEventListener('click', () => go(-1));
    q('.st-next').addEventListener('click', next);
    document.addEventListener('keydown', e => {
      if (opts.isActive && !opts.isActive()) return;
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft') go(-1);
    });
    render();
    return {go, goto(n) { i = Math.min(S.length - 1, Math.max(0, n - 1)); render(); }, length: S.length};
  }

  return {build, mount};
})();
