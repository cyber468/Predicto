(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var NS = 'http://www.w3.org/2000/svg', R = 100;

  /* ---------- radar ---------- */
  var svg = document.getElementById('radar');
  var rows = Array.prototype.slice.call(document.querySelectorAll('#traits .trait'));
  var n = rows.length, axes = [], labels = [], vertices = [];
  function pt(i, v) { var a = -Math.PI / 2 + i * 2 * Math.PI / n; return [Math.cos(a) * R * v / 100, Math.sin(a) * R * v / 100]; }
  function el(name, attrs, text, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text) e.textContent = text;
    (parent || svg).appendChild(e);
    return e;
  }
  function poly(vals) { return vals.map(function (v, i) { return pt(i, v).join(','); }).join(' '); }

  if (svg && n) {
    var defs = el('defs', {});
    var g = el('radialGradient', { id: 'sweepGrad', cx: 0, cy: 0, r: R, gradientUnits: 'userSpaceOnUse' }, null, defs);
    el('stop', { offset: '0', 'stop-color': 'currentColor', 'stop-opacity': '0.35' }, null, g);
    el('stop', { offset: '1', 'stop-color': 'currentColor', 'stop-opacity': '0' }, null, g);

    [25, 50, 75, 100].forEach(function (r) { el('polygon', { 'class': 'ring', points: poly(rows.map(function () { return r; })) }); });
    rows.forEach(function (row, i) {
      var p = pt(i, 100), l = pt(i, 118);
      axes.push(el('line', { 'class': 'axis', x1: 0, y1: 0, x2: p[0], y2: p[1] }));
      labels.push(el('text', { x: l[0], y: l[1], 'text-anchor': Math.abs(l[0]) < 8 ? 'middle' : (l[0] > 0 ? 'start' : 'end'), 'dominant-baseline': 'middle', 'font-size': 12.5, 'font-weight': 600 }, row.dataset.label));
    });
    el('polygon', { 'class': 'group', points: poly(rows.map(function (r) { return +r.dataset.group; })) });
    el('polygon', { 'class': 'mine', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-dasharray': '5 4', 'stroke-linejoin': 'round', points: poly(rows.map(function (r) { return +r.dataset.mine; })) });
    rows.forEach(function (row, i) {
      var p = pt(i, +row.dataset.group);
      var c = el('circle', { 'class': 'vertex', cx: p[0], cy: p[1], r: 4.5 });
      c.style.animationDelay = (0.9 + i * 0.12) + 's';
      vertices.push(c);
    });
    if (!reduce) {
      var end = -Math.PI / 2 + 0.9;
      el('path', { 'class': 'sweep', d: 'M0 0 L' + pt(0, 100).join(' ') + ' A' + R + ' ' + R + ' 0 0 1 ' + (Math.cos(end) * R) + ' ' + (Math.sin(end) * R) + ' Z', fill: 'url(#sweepGrad)', style: 'color: var(--accent)' });
    }

    function highlight(i) {
      svg.classList.toggle('dim', i >= 0);
      axes.forEach(function (a, k) { a.classList.toggle('hl', k === i); });
      labels.forEach(function (a, k) { a.classList.toggle('hl', k === i); });
      vertices.forEach(function (a, k) { a.classList.toggle('hl', k === i); });
    }
    rows.forEach(function (row, i) {
      row.addEventListener('mouseenter', function () { highlight(i); });
      row.addEventListener('focus', function () { highlight(i); });
      row.addEventListener('mouseleave', function () { highlight(-1); });
      row.addEventListener('blur', function () { highlight(-1); });
    });
  }

  /* ---------- count-up ---------- */
  function fmt(v) { return (Math.round(v * 100) / 100) + '%'; }
  function countUp(node, to, delay, dur) {
    var start = null;
    node.textContent = '0%';
    setTimeout(function () {
      requestAnimationFrame(function step(ts) {
        if (start === null) start = ts;
        var t = Math.min(1, (ts - start) / dur), e = 1 - Math.pow(1 - t, 3);
        node.textContent = t < 1 ? fmt(to * e) : fmt(to);
        if (t < 1) requestAnimationFrame(step);
      });
    }, delay);
  }
  if (!reduce) {
    document.querySelectorAll('#traits .num').forEach(function (nd, i) { countUp(nd, parseFloat(nd.dataset.to), 500 + i * 120, 1200); });
  }

  /* ---------- 50 answers -> five numbers ---------- */
  var dots = document.getElementById('dots');
  var steps = document.querySelectorAll('.steps li');
  var stepsWrap = document.querySelector('.steps');
  var replay = document.getElementById('replay');
  var timers = [];
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
  function setStep(k) { steps.forEach(function (s, i) { s.classList.toggle('on', i === k); }); }

  function play() {
    timers.forEach(clearTimeout); timers = [];
    dots.classList.remove('p1', 'p2', 'p3');
    dots.classList.add('armed'); stepsWrap.classList.add('armed');
    dots.querySelectorAll('.dnum').forEach(function (d) { d.textContent = '0%'; });
    setStep(-1);
    later(function () { dots.classList.add('p1'); setStep(0); }, 150);
    later(function () { dots.classList.add('p2'); setStep(1); }, 2200);
    later(function () {
      dots.classList.add('p3'); setStep(2);
      dots.querySelectorAll('.dnum').forEach(function (d, i) { countUp(d, parseFloat(d.dataset.to), i * 90, 1100); });
    }, 4200);
    later(function () { steps.forEach(function (s) { s.classList.add('on'); }); }, 7000);
  }
  if (dots && !reduce) {
    dots.classList.add('armed'); stepsWrap.classList.add('armed');
    if ('IntersectionObserver' in window) {
      var seen = false;
      new IntersectionObserver(function (es, obs) {
        if (es[0].isIntersecting && !seen) { seen = true; play(); obs.disconnect(); }
      }, { threshold: 0.35 }).observe(dots);
    } else { play(); }
    if (replay) replay.addEventListener('click', play);
  } else if (replay) { replay.hidden = true; }

  /* ---------- reveal cards on scroll ---------- */
  var cards = document.querySelector('.cards');
  if (cards && !reduce && 'IntersectionObserver' in window) {
    cards.classList.add('reveal');
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.2 });
    cards.querySelectorAll('.card').forEach(function (c, i) { c.style.transitionDelay = (i * 0.08) + 's'; io.observe(c); });
  }
})();
