// Landing page behaviour: the film controls and the figures read from facts.json.
// No framework and no build step. Every figure shown comes from facts.json, which
// scripts/sync.py writes by running the review app's own code; nothing is typed in here.
(function () {
  "use strict";

  var FILMS = {
    landscape: { src: "/media/gripper_hype_1080p.mp4", poster: "/media/poster.webp" },
    portrait: { src: "/media/gripper_hype_vertical.mp4", poster: "/media/poster_vertical.webp" },
  };
  var STATUS_WORD = { pass: "pass", risk: "at risk", fail: "fails", open: "open" };

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var phonePortrait = window.matchMedia("(max-width: 600px) and (orientation: portrait)");

  var frame = document.getElementById("film");
  var teaser = document.getElementById("teaser");
  var full = document.getElementById("full");
  var actions = document.getElementById("film-actions");
  var playBtn = document.getElementById("play-full");
  var backBtn = document.getElementById("film-back");

  /* The teaser loops silently, except for people who asked their system for less motion:
     they get the poster and nothing downloads until they press play. */
  function startTeaser() {
    if (reduced.matches || teaser.hidden) return;
    teaser.preload = "auto";
    var p = teaser.play();
    if (p && p.catch) p.catch(function () {});
  }
  function stopTeaser() {
    teaser.pause();
  }
  reduced.addEventListener("change", function () {
    if (reduced.matches) stopTeaser();
    else if (full.hidden) startTeaser();
  });
  startTeaser();

  /* One control plays the full film with sound. Portrait phones get the vertical cut. The file is
     not requested before this click. */
  playBtn.addEventListener("click", function () {
    var cut = phonePortrait.matches ? FILMS.portrait : FILMS.landscape;
    stopTeaser();
    teaser.hidden = true;
    actions.hidden = true;
    frame.classList.toggle("portrait", cut === FILMS.portrait);
    full.poster = cut.poster;
    full.preload = "auto";
    if (full.getAttribute("src") !== cut.src) full.src = cut.src;
    full.hidden = false;
    backBtn.hidden = false;
    var p = full.play();
    if (p && p.catch) p.catch(function () { full.focus(); });
  });

  backBtn.addEventListener("click", function () {
    full.pause();
    full.hidden = true;
    backBtn.hidden = true;
    frame.classList.remove("portrait");
    teaser.hidden = false;
    actions.hidden = false;
    startTeaser();
    playBtn.focus();
  });

  /* Figures. */
  var facts = document.getElementById("facts");
  var provenance = document.getElementById("provenance");

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function render(f) {
    var r = f.requirements;
    facts.textContent = "";

    var count = el("p");
    count.append("The review tracks ");
    count.append(el("b", { "data-fact": "requirements.total" }, String(r.total)));
    count.append(" requirements:");
    facts.append(count);

    var chips = el("div", { class: "chips", role: "list", "aria-label": "Requirement status counts" });
    ["pass", "risk", "open", "fail"].forEach(function (s) {
      var chip = el("span", { class: "st " + s, role: "listitem" });
      chip.append(el("span", { "data-fact": "requirements.counts." + s }, String(r.counts[s])));
      chip.append(" " + STATUS_WORD[s]);
      chips.append(chip);
    });
    facts.append(chips);

    var failing = r.items.filter(function (i) { return i.status === "fail"; });
    if (failing.length) {
      facts.append(el("p", null, "What fails today:"));
      var ul = el("ul", { class: "fails", id: "fails" });
      failing.forEach(function (i) {
        var li = el("li");
        var b = el("b", null, i.name);
        li.append(b);
        li.append(el("span", null, i.evidence));
        if (i.evidenceId) {
          var a = el("a", { href: "/review/#" + i.evidenceId, "aria-label": "See the evidence in the review: " + i.name }, "See the evidence in the review");
          li.append(a);
        }
        ul.append(li);
      });
      facts.append(ul);
    }

    var waiting = el("p");
    waiting.append(el("b", { "data-fact": "decisions.total" }, String(f.decisions.total)));
    waiting.append(" decisions need a ruling and ");
    waiting.append(el("b", { "data-fact": "bench_checks.total" }, String(f.bench_checks.total)));
    waiting.append(" bench checks are waiting. ");
    waiting.append(el("a", { href: "/review/#open-requirements" }, "Read every open item"));
    facts.append(waiting);

    if (provenance && f.source) {
      provenance.textContent =
        "Figures read from the design review at source commit " + f.source.commit.slice(0, 7) + ", " + f.source.committed.slice(0, 10) + ".";
    }
  }

  function fallback() {
    facts.textContent = "";
    var p = el("p");
    p.append("The current counts could not be loaded. ");
    p.append(el("a", { href: "/review/#open-requirements" }, "Read them in the review"));
    p.append(".");
    facts.append(p);
  }

  fetch("/facts.json", { cache: "no-cache" })
    .then(function (res) {
      if (!res.ok) throw new Error("facts.json " + res.status);
      return res.json();
    })
    .then(render)
    .catch(fallback);
})();
