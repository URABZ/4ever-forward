(() => {
  function installMobileStabilityFix() {
    const guide = document.getElementById('ffGuide');
    if (!guide || guide.dataset.mobileStabilityFix === '3') return;
    guide.dataset.mobileStabilityFix = '3';

    const accessButtons = () => Array.from(
      guide.querySelectorAll('.ff-option[data-access]')
    );

    let lastHandledAt = 0;
    let lastHandledValue = '';

    function onAccessStep() {
      return guide.classList.contains('open') &&
        guide.querySelector('.ff-step.active')?.dataset.step === '3';
    }

    function forceSelect(button) {
      if (!button || !button.dataset.access) return;

      const now = Date.now();
      const value = button.dataset.access;
      if (value === lastHandledValue && now - lastHandledAt < 180) return;
      lastHandledAt = now;
      lastHandledValue = value;

      // Run the original 4EVER FORWARD handler so the closure-scoped
      // accessBarrier value is updated for resource ranking.
      if (typeof button.onclick === 'function') {
        try { button.onclick.call(button); } catch (_) {}
      }

      accessButtons().forEach((b) => {
        const selected = b === button;
        b.classList.toggle('selected', selected);
        b.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });

      try {
        if (navigator.vibrate) navigator.vibrate(20);
      } catch (_) {}
    }

    function prepareButtons() {
      accessButtons().forEach((button) => {
        if (button.dataset.ffTouchReady === '1') return;
        button.dataset.ffTouchReady = '1';
        button.disabled = false;
        button.removeAttribute('disabled');
        button.removeAttribute('aria-disabled');
        button.setAttribute('role', 'button');
        button.setAttribute('aria-pressed',
          button.classList.contains('selected') ? 'true' : 'false');

        button.addEventListener('click', (event) => {
          if (!onAccessStep()) return;
          event.preventDefault();
          forceSelect(button);
        }, true);

        button.addEventListener('pointerup', (event) => {
          if (!onAccessStep()) return;
          event.preventDefault();
          forceSelect(button);
        }, true);

        button.addEventListener('touchend', () => {
          if (!onAccessStep()) return;
          forceSelect(button);
        }, { capture: true, passive: true });
      });
    }

    // Coordinate fallback for iPhone/Safari in case another transparent/fixed
    // layer steals the normal event target.
    document.addEventListener('pointerup', (event) => {
      if (!onAccessStep()) return;
      const x = event.clientX;
      const y = event.clientY;
      const hit = accessButtons().find((button) => {
        const r = button.getBoundingClientRect();
        return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
      });
      if (hit) forceSelect(hit);
    }, true);

    document.addEventListener('touchend', (event) => {
      if (!onAccessStep()) return;
      const t = event.changedTouches && event.changedTouches[0];
      if (!t) return;
      const hit = accessButtons().find((button) => {
        const r = button.getBoundingClientRect();
        return t.clientX >= r.left && t.clientX <= r.right &&
               t.clientY >= r.top && t.clientY <= r.bottom;
      });
      if (hit) forceSelect(hit);
    }, { capture: true, passive: true });

    // Hide floating launchers while the Simple Flow is open so they cannot
    // cover Transportation or any other next-step choice.
    function syncLaunchers() {
      const open = guide.classList.contains('open');
      ['ffCloudOpen', 'v33StartLauncher'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
          el.style.visibility = open ? 'hidden' : '';
          el.style.pointerEvents = open ? 'none' : '';
        }
      });
    }

    new MutationObserver(() => {
      prepareButtons();
      syncLaunchers();
    }).observe(guide, {
      attributes: true,
      attributeFilter: ['class'],
      subtree: true,
      childList: true
    });

    const style = document.createElement('style');
    style.id = 'ff-mobile-stability-fix-style';
    style.textContent = `
      body.ff-simple-flow-open #ffCloudOpen,
      body.ff-simple-flow-open #v33StartLauncher{
        display:none !important;
        pointer-events:none !important;
      }

      #ffGuide #ffAccessOptions{
        position:relative !important;
        z-index:10002 !important;
      }
      #ffGuide .ff-option[data-access]{
        pointer-events:auto !important;
        touch-action:manipulation !important;
        -webkit-tap-highlight-color:rgba(247,201,40,.28) !important;
        position:relative !important;
        z-index:10003 !important;
        -webkit-user-select:none !important;
        user-select:none !important;
      }
      #ffGuide .ff-option[data-access].selected{
        background:#fff3a8 !important;
        border-color:#f2c400 !important;
        color:#111 !important;
        box-shadow:0 0 0 3px rgba(242,196,0,.22) !important;
      }
      #ffGuide .ff-option[data-access].selected::after{
        content:" ✓";
        font-weight:900;
      }
      #ffGuide .ff-actions{
        position:sticky !important;
        bottom:0 !important;
        z-index:10010 !important;
        background:#fff !important;
        pointer-events:auto !important;
      }
      #ffGuide #ffNext{
        pointer-events:auto !important;
        touch-action:manipulation !important;
      }

      #ffCloudPanel,
      #ffCloudPanel .ff-cloud-card{
        overflow-x:hidden !important;
        max-width:100vw !important;
      }
      #ffCloudPanel .ff-cloud-toggle{
        display:flex !important;
        align-items:flex-start !important;
        gap:10px !important;
        width:100% !important;
        min-width:0 !important;
        overflow:hidden !important;
      }
      #ffCloudPanel .ff-cloud-toggle input[type="checkbox"]{
        width:22px !important;
        min-width:22px !important;
        max-width:22px !important;
        height:22px !important;
        padding:0 !important;
        margin:2px 0 0 !important;
        flex:0 0 22px !important;
        border-radius:6px !important;
        accent-color:#111;
      }
      #ffCloudPanel .ff-cloud-toggle span{
        display:block !important;
        min-width:0 !important;
        width:auto !important;
        overflow-wrap:anywhere !important;
      }
      #ffCloudPanel .ff-cloud-btn{
        max-width:100% !important;
        white-space:normal !important;
      }
    `;
    document.getElementById(style.id)?.remove();
    document.head.appendChild(style);

    prepareButtons();
    syncLaunchers();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installMobileStabilityFix, { once: true });
  } else {
    installMobileStabilityFix();
  }
})();
