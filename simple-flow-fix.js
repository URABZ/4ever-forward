(() => {
  function installSimpleFlowMobileBehavior() {
    const guide = document.getElementById("ffGuide");
    if (!guide || guide.dataset.simpleFlowMobileBehavior === "5") return;
    guide.dataset.simpleFlowMobileBehavior = "5";

    const accessButtons = () =>
      Array.from(guide.querySelectorAll(".ff-option[data-access]"));
    const activeStep = () =>
      guide.querySelector(".ff-step.active")?.dataset.step || "";
    const onAccessStep = () =>
      guide.classList.contains("open") && activeStep() === "3";
    const accessSelected = () =>
      accessButtons().some((button) => button.classList.contains("selected"));

    function safetyAnsweredIfRequired() {
      const safety = document.getElementById("ffSafetyQuestion");
      const required = !!safety && getComputedStyle(safety).display !== "none";
      return !required || !!guide.querySelector(".ff-option[data-safe].selected");
    }

    let advanceTimer;
    let advancing = false;

    function scheduleAdvance() {
      if (!onAccessStep() || !accessSelected() || !safetyAnsweredIfRequired()) return;
      window.clearTimeout(advanceTimer);
      advanceTimer = window.setTimeout(() => {
        advanceTimer = undefined;
        if (
          advancing ||
          !onAccessStep() ||
          !accessSelected() ||
          !safetyAnsweredIfRequired() ||
          typeof window.ffNext !== "function"
        ) return;

        // Keep Step 3's one-choice-at-a-time behavior, using the same transition
        // as the visible Find My Next Step button.
        advancing = true;
        window.ffNext();
        window.setTimeout(() => { advancing = false; }, 400);
      }, 220);
    }

    // Let the existing button onclick update its private ranking/safety state
    // first, then advance once. Native mobile taps synthesize this same click;
    // no parallel touch, pointer, or coordinate handlers are needed.
    guide.addEventListener("click", (event) => {
      const target = event.target;
      if (!target || typeof target.closest !== "function") return;
      const choice = target.closest(".ff-option[data-access], .ff-option[data-safe]");
      if (!choice || !onAccessStep()) return;

      window.setTimeout(() => {
        accessButtons().forEach((button) => {
          button.setAttribute(
            "aria-pressed",
            button.classList.contains("selected") ? "true" : "false"
          );
        });
        scheduleAdvance();
      }, 0);

      if (choice.hasAttribute("data-access")) {
        try {
          if (navigator.vibrate) navigator.vibrate(20);
        } catch (_) {}
      }
    });

    function syncLaunchers() {
      const open = guide.classList.contains("open");
      ["ffCloudOpen", "v33StartLauncher"].forEach((id) => {
        const element = document.getElementById(id);
        if (element) {
          element.style.visibility = open ? "hidden" : "";
          element.style.pointerEvents = open ? "none" : "";
        }
      });
    }

    // Only track the modal's open state. Do not observe result-card mutations.
    new MutationObserver(syncLaunchers).observe(guide, {
      attributes: true,
      attributeFilter: ["class"],
    });

    const style = document.createElement("style");
    style.id = "ff-mobile-stability-fix-style";
    style.textContent = `
      body.ff-simple-flow-open #ffCloudOpen,
      body.ff-simple-flow-open #v33StartLauncher {
        display: none !important;
        pointer-events: none !important;
      }
      #ffGuide #ffAccessOptions {
        position: relative !important;
        z-index: 10002 !important;
      }
      #ffGuide .ff-option[data-access] {
        pointer-events: auto !important;
        touch-action: manipulation !important;
        -webkit-tap-highlight-color: rgba(247, 201, 40, .28) !important;
        position: relative !important;
        z-index: 10003 !important;
        -webkit-user-select: none !important;
        user-select: none !important;
      }
      #ffGuide .ff-option[data-access].selected {
        background: #fff3a8 !important;
        border-color: #f2c400 !important;
        color: #111 !important;
        box-shadow: 0 0 0 3px rgba(242, 196, 0, .22) !important;
      }
      #ffGuide .ff-option[data-access].selected::after {
        content: " ✓";
        font-weight: 900;
      }
      #ffGuide .ff-actions {
        position: sticky !important;
        bottom: 0 !important;
        z-index: 10010 !important;
        background: #fff !important;
        pointer-events: auto !important;
      }
      #ffGuide #ffNext {
        pointer-events: auto !important;
        touch-action: manipulation !important;
        position: relative !important;
        z-index: 10011 !important;
      }
      #ffCloudPanel,
      #ffCloudPanel .ff-cloud-card {
        overflow-x: hidden !important;
        max-width: 100vw !important;
      }
      #ffCloudPanel .ff-cloud-toggle {
        display: flex !important;
        align-items: flex-start !important;
        gap: 10px !important;
        width: 100% !important;
        min-width: 0 !important;
        overflow: hidden !important;
      }
      #ffCloudPanel .ff-cloud-toggle input[type="checkbox"] {
        width: 22px !important;
        min-width: 22px !important;
        max-width: 22px !important;
        height: 22px !important;
        padding: 0 !important;
        margin: 2px 0 0 !important;
        flex: 0 0 22px !important;
        border-radius: 6px !important;
        accent-color: #111;
      }
      #ffCloudPanel .ff-cloud-toggle span {
        display: block !important;
        min-width: 0 !important;
        width: auto !important;
        overflow-wrap: anywhere !important;
      }
      #ffCloudPanel .ff-cloud-btn {
        max-width: 100% !important;
        white-space: normal !important;
      }
    `;

    document.getElementById(style.id)?.remove();
    document.head.appendChild(style);
    syncLaunchers();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", installSimpleFlowMobileBehavior, {
      once: true,
    });
  } else {
    installSimpleFlowMobileBehavior();
  }
})();