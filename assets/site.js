(function(){
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var els = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || reduce) {
    els.forEach(function(e){ e.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){ if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, {threshold: 0.15});
    els.forEach(function(e){ io.observe(e); });
  }

  // Scroll progress + sticky header shadow
  var bar = document.querySelector(".progress"), top = document.querySelector("header.top");
  function onScroll(){
    var h = document.documentElement, max = h.scrollHeight - h.clientHeight;
    if (bar) bar.style.transform = "scaleX(" + (max > 0 ? Math.min(1, h.scrollTop / max) : 0) + ")";
    if (top) top.classList.toggle("stuck", h.scrollTop > 8);
  }
  addEventListener("scroll", onScroll, {passive: true}); onScroll();

  // Card spotlight follows the pointer
  document.querySelectorAll(".tcard,.guide").forEach(function(c){
    c.addEventListener("pointermove", function(e){
      var r = c.getBoundingClientRect();
      c.style.setProperty("--mx", (e.clientX - r.left) + "px");
      c.style.setProperty("--my", (e.clientY - r.top) + "px");
    });
  });

  // Lead form -> WhatsApp message (nothing is stored)
  var lf = document.getElementById("lead-form");
  if (lf) {
    var ld = JSON.parse(document.getElementById("lead-data").textContent);
    lf.addEventListener("submit", function(e){
      e.preventDefault();
      var f = lf.elements, ok = true;
      ["n","p"].forEach(function(k){ var bad = !f[k].value.trim(); f[k].classList.toggle("bad", bad); if (bad) ok = false; });
      if (!ok) return;
      var body = ld.msg.replace("{c}", f.c.value).replace("{g}", f.g.value).replace("{n}", f.n.value.trim())
        .replace("{p}", f.cc.value + " " + f.p.value.trim()).replace("{l}", f.l.value);
      var url = ld.wa + encodeURIComponent(ld.hello + "\n" + body + "\n" + ld.tag);
      window.open(url, "_blank", "noopener") || (location.href = url);
    });
  }

  // Language picker closes on outside tap or Escape
  var ls = document.querySelector(".langsel");
  if (ls) {
    document.addEventListener("click", function(e){ if (!ls.contains(e.target)) ls.removeAttribute("open"); });
    document.addEventListener("keydown", function(e){ if (e.key === "Escape") ls.removeAttribute("open"); });
  }

  // Count-up numbers (final value is already in the HTML)
  var counts = document.querySelectorAll("[data-count]");
  if (counts.length && "IntersectionObserver" in window && !reduce) {
    var cio = new IntersectionObserver(function(es){
      es.forEach(function(en){
        if (!en.isIntersecting) return; cio.unobserve(en.target);
        var el = en.target, to = +el.getAttribute("data-count"), t0 = performance.now(), dur = 1800;
        var fmt = new Intl.NumberFormat(el.getAttribute("data-lang") === "en" ? "en-US" : el.getAttribute("data-lang"));
        (function step(t){
          var k = Math.min(1, (t - t0) / dur), v = Math.round(to * (1 - Math.pow(1 - k, 3)));
          el.textContent = fmt.format(v) + "+";
          if (k < 1) requestAnimationFrame(step);
        })(t0);
      });
    }, {threshold: 0.4});
    counts.forEach(function(c){ cio.observe(c); });
  }

  // Norwood selector -> WhatsApp message
  var dataEl = document.getElementById("nor-data");
  if (dataEl) {
    var d = JSON.parse(dataEl.textContent);
    var btns = document.querySelectorAll(".stage");
    var desc = document.getElementById("nor-desc");
    var cta = document.getElementById("nor-cta");
    var cur = 0;
    function link() {
      var radio = document.querySelector('input[name="int"]:checked');
      var interest = radio ? radio.value : "";
      var msg = d.tpl.replace("{stage}", cur).replace("{interest}", interest) + " " + d.tag;
      cta.href = d.wa + encodeURIComponent(msg);
    }
    btns.forEach(function(b){
      b.addEventListener("click", function(){
        cur = +b.getAttribute("data-n");
        btns.forEach(function(x){ x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        desc.textContent = d.stage.replace("{n}", cur) + ". " + d.desc[cur - 1];
        cta.textContent = d.cta.replace("{n}", cur);
        link();
      });
    });
    document.querySelectorAll('input[name="int"]').forEach(function(r){ r.addEventListener("change", function(){ if (cur) link(); }); });
  }

  // Results lightbox
  var imgs = document.querySelectorAll(".gallery img");
  if (imgs.length && window.HTMLDialogElement) {
    var dlg = document.createElement("dialog"); dlg.className = "lb";
    var big = document.createElement("img"); dlg.appendChild(big); document.body.appendChild(dlg);
    dlg.addEventListener("click", function(){ dlg.close(); });
    imgs.forEach(function(i){ i.addEventListener("click", function(){ big.src = i.currentSrc || i.src; big.alt = i.alt; dlg.showModal(); }); });
  }
})();
