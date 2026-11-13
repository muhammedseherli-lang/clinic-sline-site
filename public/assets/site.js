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
    imgs.forEach(function(i){ i.addEventListener("click", function(){ big.src = i.src; big.alt = i.alt; dlg.showModal(); }); });
  }
})();
