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
    else if (full.hidden && (!explainer || explainer.paused)) startTeaser();
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

  /* Optional inline disclosure: the ordinary doors remain usable with no guide or script. */
  var tourSteps = [
    { title: "Begin with a question", copy: "This is a design record, not proof of a working prototype. The next stops show where to inspect the mechanism, question its clearances, check the assembly and find the claims still waiting for a test." },
    { title: "See the model", copy: "Start with the gripper on the arm wrist. Drag to orbit, move the jaw slider, then use Explode to see how the fingers and housing relate. Ask whether the proposed motion makes sense before reading the calculations.", door: "door-model" },
    { title: "Check the fits", copy: "Look for the servo horn clearance finding. Read the measured gap and the method behind it. A CAD clearance is a prediction; it still needs to survive manufacturing and a real assembly.", door: "door-fit" },
    { title: "Follow the assembly", copy: "Step through the build order and watch parts enter along their intended paths. Check tool reach and the at-risk steps. A part fitting in its final position does not prove it can be installed.", door: "door-assembly" },
    { title: "Read what is still open", copy: "Finish with the requirement statuses, unresolved decisions and bench checks. Separate calculation from measurement. Use the failed and at-risk items to decide what a first prototype must establish.", door: "door-open" },
  ];
  var tourIndex = 0;
  var tourStart = document.getElementById("start-tour");
  var tourPanel = document.getElementById("tour-panel");
  var tourTitle = document.getElementById("tour-title");
  var tourCopy = document.getElementById("tour-copy");
  var tourLink = document.getElementById("tour-link");
  var tourBack = document.getElementById("tour-back");
  var tourNext = document.getElementById("tour-next");
  var tourMotion;

  function clearTourStop() {
    document.querySelectorAll(".door[aria-current]").forEach(function (door) { door.removeAttribute("aria-current"); });
  }
  function showTourStep() {
    var step = tourSteps[tourIndex];
    clearTourStop();
    tourTitle.textContent = step.title;
    tourCopy.textContent = step.copy;
    document.getElementById("tour-progress").textContent = "Step " + (tourIndex + 1) + " of " + tourSteps.length;
    tourBack.disabled = tourIndex === 0;
    tourNext.textContent = tourIndex === tourSteps.length - 1 ? "Finish tour" : "Next";
    tourLink.hidden = !step.door;
    if (step.door) {
      var door = document.getElementById(step.door);
      door.setAttribute("aria-current", "step");
      tourLink.href = door.getAttribute("href");
      tourLink.textContent = {
        "door-model": "Open the model",
        "door-fit": "Open the fit findings",
        "door-assembly": "Open the assembly",
        "door-open": "Open the remaining work"
      }[step.door];
    } else tourLink.removeAttribute("href");
    if (tourMotion) tourMotion.cancel();
    if (!reduced.matches) {
      var motionTokens = getComputedStyle(document.documentElement);
      tourMotion = document.getElementById("tour-content").animate(
        [{ opacity: .65, transform: "translateY(" + motionTokens.getPropertyValue("--s2").trim() + ")" }, { opacity: 1, transform: "none" }],
        { duration: parseFloat(motionTokens.getPropertyValue("--motion-step")), easing: motionTokens.getPropertyValue("--motion-ease").trim() }
      );
    }
    tourTitle.focus({ preventScroll: true });
  }
  function closeTour() {
    if (tourMotion) tourMotion.cancel();
    tourPanel.hidden = true;
    tourStart.setAttribute("aria-expanded", "false");
    clearTourStop();
    tourStart.focus({ preventScroll: true });
  }
  tourStart.hidden = false;
  tourStart.addEventListener("click", function () {
    if (!tourPanel.hidden) return closeTour();
    tourIndex = 0;
    tourPanel.hidden = false;
    tourStart.setAttribute("aria-expanded", "true");
    showTourStep();
    tourPanel.scrollIntoView({ block: "nearest", behavior: reduced.matches ? "instant" : "smooth" });
  });
  document.getElementById("close-tour").addEventListener("click", closeTour);
  tourBack.addEventListener("click", function () { if (tourIndex > 0) { tourIndex--; showTourStep(); } });
  tourNext.addEventListener("click", function () {
    if (tourIndex === tourSteps.length - 1) return closeTour();
    tourIndex++; showTourStep();
  });
  tourPanel.addEventListener("keydown", function (event) {
    if (event.key === "Escape") { event.preventDefault(); closeTour(); }
  });
  reduced.addEventListener("change", function () { if (reduced.matches && tourMotion) tourMotion.cancel(); });

  /* Observe one explanatory sequence, once. Never hide content behind the observer. */
  if ("IntersectionObserver" in window) {
    var sequence = document.querySelector(".mechanism");
    var observer = new IntersectionObserver(function (entries) {
      if (entries.some(function (entry) { return entry.isIntersecting; })) {
        sequence.classList.add("in-view");
        observer.disconnect();
      }
    }, { threshold: .3 });
    observer.observe(sequence);
  }

  /* No src or caption track exists until an explicit play. Closing releases both. */
  var explainer = document.getElementById("explainer");
  var explainerPlay = document.getElementById("play-explainer");
  var explainerClose = document.getElementById("close-explainer");
  var explainerStatus = document.getElementById("explainer-status");
  explainer.controls = false;
  explainerPlay.hidden = false;
  explainerPlay.addEventListener("click", function () {
    full.pause();
    stopTeaser();
    explainerStatus.textContent = "Loading the captioned walkthrough…";
    explainerPlay.hidden = true;
    explainerClose.hidden = false;
    explainer.controls = true;
    if (!explainer.querySelector("track")) {
      var track = document.createElement("track");
      track.kind = "captions";
      track.label = "English";
      track.srclang = "en";
      track.default = true;
      track.src = "/media/review-walkthrough.vtt";
      explainer.append(track);
      track.track.mode = "showing";
    }
    explainer.src = "/media/review-walkthrough.mp4";
    var promise = explainer.play();
    if (promise && promise.catch) promise.catch(function () {
      if (explainer.error) return;
      explainerStatus.textContent = "Use the video controls to begin playback. Captions included; no audio.";
      explainer.focus();
    });
  });
  explainer.addEventListener("playing", function () { explainerStatus.textContent = "Captions included; no audio. Pause or seek with the video controls."; });
  explainer.addEventListener("error", function () {
    explainerStatus.textContent = "The walkthrough could not be played. Try play again, or follow the guided tour above.";
    explainerPlay.hidden = false;
    explainerPlay.textContent = "Try the walkthrough again";
  });
  explainerClose.addEventListener("click", function () {
    explainer.pause();
    explainer.removeAttribute("src");
    explainer.querySelectorAll("track").forEach(function (track) { track.remove(); });
    explainer.load();
    explainer.controls = false;
    explainerClose.hidden = true;
    explainerPlay.hidden = false;
    explainerPlay.textContent = "Play the walkthrough";
    explainerStatus.textContent = "Captions included; no audio. Use full screen for the review details.";
    explainerPlay.focus();
    if (full.hidden) startTeaser();
  });
  playBtn.addEventListener("click", function () { explainer.pause(); });

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
