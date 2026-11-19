(function () {
  var form = document.getElementById('quiz');
  if (!form) return;
  document.documentElement.classList.add('js');
  var items = Array.prototype.slice.call(form.querySelectorAll('.item'));
  var segs = form.querySelectorAll('.seg i');
  var back = document.getElementById('back'), next = document.getElementById('next'), finish = document.getElementById('finish');
  var cur = document.getElementById('cur');
  var perTrait = 10, i = 0, timer = null, last = items.length - 1;

  function answered(n) { return !!items[n].querySelector('input:checked'); }

  function render() {
    items.forEach(function (it, n) { it.classList.toggle('on', n === i); });
    cur.textContent = i + 1;
    back.style.visibility = i === 0 ? 'hidden' : 'visible';
    next.hidden = !(i < last && answered(i));
    finish.hidden = !(i === last && answered(i));
    segs.forEach(function (s, t) {
      var done = 0;
      for (var k = t * perTrait; k < (t + 1) * perTrait; k++) if (answered(k)) done++;
      s.style.width = (done / perTrait * 100) + '%';
    });
  }

  function focusItem() {
    var target = items[i].querySelector('input:checked') || items[i].querySelector('input');
    if (target) target.focus({ preventScroll: true });
  }

  function go(n) { clearTimeout(timer); timer = null; i = Math.max(0, Math.min(last, n)); render(); focusItem(); }

  // One pending advance at a time, tied to the question it was scheduled for.
  function advanceSoon() {
    if (i >= last || timer) return;
    var from = i;
    timer = setTimeout(function () { timer = null; if (i === from) go(from + 1); }, 160);
  }

  function pick(n) {
    var radio = items[i].querySelector('input[value="' + n + '"]');
    if (!radio) return;
    radio.checked = true;
    render();
    advanceSoon();
  }

  form.addEventListener('change', render);
  // Mouse or touch clicks advance. Arrow keys and Space on a focused radio only select (event.detail is 0).
  form.addEventListener('click', function (e) {
    if (e.target.type === 'radio' && e.detail > 0) advanceSoon();
  });
  back.addEventListener('click', function () { go(i - 1); });
  next.addEventListener('click', function () { go(i + 1); });
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.target.tagName === 'INPUT' && e.target.type !== 'radio') return;
    if (/^[1-5]$/.test(e.key)) { e.preventDefault(); pick(e.key); }
  });
  render();
  focusItem();
})();
