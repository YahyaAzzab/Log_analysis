/**
 * STRIX intro sequence (~3s) with GSAP.
 * Plays on every page load, skippable, respects prefers-reduced-motion.
 */
(function () {
  "use strict";

  var intro = document.getElementById("intro");
  var dashboard = document.getElementById("dashboard");
  var logoFly = document.getElementById("intro-logo-fly");
  var owl = document.getElementById("intro-owl");
  var progressBar = document.getElementById("intro-progress-bar");
  var subtitle = document.getElementById("intro-subtitle");
  var letters = document.querySelectorAll(".intro__letter");
  var drawPaths = document.querySelectorAll(".intro-draw");
  var pupils = document.querySelectorAll(".intro-pupil");
  var logoSlot = document.getElementById("header-logo-slot");
  var sidebarLogo = document.querySelector(".sidebar__logo");
  var dashItems = document.querySelectorAll(".dash-item");

  if (!intro || !dashboard || typeof gsap === "undefined") {
    showDashboardImmediate();
    return;
  }

  var prefersReduced =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finished = false;

  if (prefersReduced) {
    showDashboardImmediate();
    return;
  }

  prepareStrokePaths(drawPaths);

  var timeline = gsap.timeline({
    defaults: { ease: "power2.out" },
  });

  var skipHandler = function (event) {
    if (event.type === "keydown" && event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    skipIntro();
  };

  document.addEventListener("keydown", skipHandler);
  intro.addEventListener("click", skipHandler);

  timeline
    .set(pupils, { opacity: 0 })
    .set(letters, { opacity: 0, y: 12 })
    .set(subtitle, { opacity: 0, y: 8 })
    .set(progressBar, { width: "0%" })
    .to(
      drawPaths,
      {
        strokeDashoffset: 0,
        duration: 1.15,
        stagger: 0.05,
        ease: "power1.inOut",
      },
      0
    )
    .to(progressBar, { width: "100%", duration: 2.8, ease: "none" }, 0)
    .to(
      pupils,
      {
        opacity: 1,
        duration: 0.35,
        stagger: 0.08,
        onStart: function () {
          owl.classList.add("is-eyes-lit");
        },
      },
      1.0
    )
    .to(
      letters,
      {
        opacity: 1,
        y: 0,
        duration: 0.28,
        stagger: 0.07,
        ease: "power2.out",
      },
      1.25
    )
    .to(subtitle, { opacity: 1, y: 0, duration: 0.45 }, 1.85)
    .add(function () {
      handoffToHeader();
    }, 2.85);

  function prepareStrokePaths(nodes) {
    nodes.forEach(function (node) {
      var length = 0;
      try {
        length = node.getTotalLength();
      } catch (err) {
        length = 240;
      }
      node.style.strokeDasharray = String(length);
      node.style.strokeDashoffset = String(length);
    });
  }

  function revealDashboardShell() {
    dashboard.classList.remove("is-hidden");
    dashboard.classList.add("is-visible");
    dashboard.setAttribute("aria-hidden", "false");
  }

  function handoffToHeader() {
    if (finished) {
      return;
    }

    revealDashboardShell();

    var slotRect = logoSlot.getBoundingClientRect();
    var flyRect = logoFly.getBoundingClientRect();
    var scale = slotRect.width / Math.max(flyRect.width, 1);
    var deltaX =
      slotRect.left +
      slotRect.width / 2 -
      (flyRect.left + flyRect.width / 2);
    var deltaY =
      slotRect.top +
      slotRect.height / 2 -
      (flyRect.top + flyRect.height / 2);

    gsap
      .timeline({
        defaults: { ease: "power2.inOut" },
        onComplete: completeIntro,
      })
      .to(
        [subtitle, letters, ".intro__hint", ".intro__progress"],
        { opacity: 0, duration: 0.35 },
        0
      )
      .to(
        logoFly,
        {
          x: deltaX,
          y: deltaY,
          scale: scale,
          duration: 0.7,
        },
        0.05
      )
      .to(
        intro,
        {
          opacity: 0,
          duration: 0.45,
        },
        0.35
      )
      .to(
        dashItems,
        {
          opacity: 1,
          y: 0,
          duration: 0.45,
          stagger: 0.07,
          ease: "power2.out",
        },
        0.4
      )
      .add(function () {
        if (sidebarLogo) {
          gsap.set(sidebarLogo, { opacity: 1 });
        }
        gsap.set(logoFly, { opacity: 0 });
      }, 0.75);
  }

  function skipIntro() {
    if (finished) {
      return;
    }
    cleanupSkipListeners();
    timeline.kill();
    gsap.killTweensOf([
      drawPaths,
      pupils,
      letters,
      subtitle,
      progressBar,
      logoFly,
      intro,
      dashItems,
    ]);

    revealDashboardShell();
    gsap.set(intro, { opacity: 0 });
    gsap.set(logoFly, { opacity: 0 });
    gsap.set(dashItems, { opacity: 1, y: 0 });
    if (sidebarLogo) {
      gsap.set(sidebarLogo, { opacity: 1 });
    }
    completeIntro();
  }

  function completeIntro() {
    if (finished) {
      return;
    }
    finished = true;
    cleanupSkipListeners();
    intro.classList.add("is-done");
    intro.setAttribute("aria-hidden", "true");
    intro.style.pointerEvents = "none";
    window.dispatchEvent(new Event("strix-dashboard-visible"));
  }

  function showDashboardImmediate() {
    if (intro) {
      intro.classList.add("is-done");
      intro.setAttribute("aria-hidden", "true");
      intro.style.display = "none";
    }
    revealDashboardShell();
    if (sidebarLogo) {
      sidebarLogo.style.opacity = "1";
    }
    dashItems.forEach(function (item) {
      item.style.opacity = "1";
      item.style.transform = "none";
    });
    window.dispatchEvent(new Event("strix-dashboard-visible"));
  }

  function cleanupSkipListeners() {
    document.removeEventListener("keydown", skipHandler);
    intro.removeEventListener("click", skipHandler);
  }
})();
