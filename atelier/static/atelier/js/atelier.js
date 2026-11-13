/* Ателье — сценарии интерфейса на чистом JavaScript (без библиотек). */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* 1. Боковое меню на телефоне */
  var side = document.getElementById("side"), scrim = document.getElementById("scrim"), menuBtn = document.getElementById("menuBtn");
  function toggleMenu(open) {
    if (!side) return;
    var on = typeof open === "boolean" ? open : !side.classList.contains("is-open");
    side.classList.toggle("is-open", on);
    if (scrim) scrim.classList.toggle("is-open", on);
    if (menuBtn) menuBtn.setAttribute("aria-expanded", on ? "true" : "false");
  }
  if (menuBtn) menuBtn.addEventListener("click", function () { toggleMenu(); });
  if (scrim) scrim.addEventListener("click", function () { toggleMenu(false); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") toggleMenu(false); });

  /* 2. Сантиметровая лента: подписи каждые 10 см */
  var tape = document.querySelector(".side__tape");
  if (tape) {
    var h = tape.offsetHeight || window.innerHeight;
    for (var y = 40, n = 10; y < h; y += 40, n += 10) {
      var s = document.createElement("span");
      s.textContent = n; s.style.top = y + "px";
      tape.appendChild(s);
    }
  }

  /* 3. Уведомления: закрытие по кнопке и автоматически через 7 секунд */
  function hideToast(t) {
    if (!t || t.classList.contains("is-hiding")) return;
    t.classList.add("is-hiding");
    setTimeout(function () { t.remove(); }, reduce ? 0 : 260);
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-close]");
    if (b) hideToast(b.closest(".toast"));
  });
  document.querySelectorAll(".toast").forEach(function (t) { setTimeout(function () { hideToast(t); }, 7000); });

  /* 4. Строки таблиц и элементы списков — ссылки */
  document.querySelectorAll("[data-href]").forEach(function (r) {
    r.addEventListener("click", function (e) {
      if (e.target.closest("a,button,form,input,select,textarea,label")) return;
      if (e.ctrlKey || e.metaKey) window.open(r.dataset.href); else window.location = r.dataset.href;
    });
  });

  /* 5. Показатели на панели: плавный счёт до значения */
  document.querySelectorAll("[data-count]").forEach(function (el) {
    var end = parseFloat(el.dataset.count);
    if (!isFinite(end) || reduce) return;
    var t0 = null, dur = 650;
    function fmt(v) { return Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0"); }
    function step(ts) {
      if (!t0) t0 = ts;
      var p = Math.min(1, (ts - t0) / dur), k = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(end * k);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });

  /* 6. Вход: показать/скрыть пароль и подстановка тестовых учётных записей */
  document.querySelectorAll("[data-pwd]").forEach(function (b) {
    b.addEventListener("click", function () {
      var i = document.getElementById(b.dataset.pwd), show = i.type === "password";
      i.type = show ? "text" : "password";
      b.setAttribute("aria-label", show ? "Скрыть пароль" : "Показать пароль");
      b.querySelector("use").setAttribute("href", show ? "#i-eye-off" : "#i-eye");
    });
  });
  document.querySelectorAll("[data-login]").forEach(function (b) {
    b.addEventListener("click", function () {
      var u = document.getElementById("u"), p = document.getElementById("p");
      if (!u || !p) return;
      u.value = b.dataset.login; p.value = b.dataset.pass; p.focus();
    });
  });

  /* 7. Отмена записи: подтверждение перед удалением */
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!window.confirm(f.dataset.confirm)) e.preventDefault(); });
  });
})();
