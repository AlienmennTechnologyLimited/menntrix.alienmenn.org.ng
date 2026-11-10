// ============================================================
// MENNTRIX CALL INITIATOR
// Hooks .mnx-call-start elements, sends a start call request,
// shows a "Calling…" bar, polls for accept/reject, then
// redirects to the call room. Uses toast notifications for
// non-success responses instead of alert().
// ============================================================

(function () {
    'use strict';

    const POLL_MS = 2000;
    const TOAST_TIMEOUT_MS = 3500;

    let pollTimer = null;
    let currentCallId = null;

    // ------------------------------------------------------------
    // CALLING BAR
    // ------------------------------------------------------------
    function ensureBar() {
        let bar = document.getElementById('mnx-calling-bar');
        if (bar) return bar;
        bar = document.createElement('div');
        bar.id = 'mnx-calling-bar';
        bar.className = 'mnx-calling-bar';
        bar.innerHTML = `
            <div class="mnx-calling-inner">
                <span class="mnx-calling-dot"></span>
                <span class="mnx-calling-text" id="mnx-calling-text">Calling…</span>
                <button type="button" class="mnx-calling-cancel" id="mnx-calling-cancel">CANCEL</button>
            </div>
        `;
        document.body.appendChild(bar);
        return bar;
    }

    function showBar(text) {
        const bar = ensureBar();
        document.getElementById('mnx-calling-text').textContent = text || 'Calling…';
        bar.classList.add('mnx-calling-show');
        document.getElementById('mnx-calling-cancel').onclick = cancelCall;
    }

    function setBarText(text) {
        const el = document.getElementById('mnx-calling-text');
        if (el) el.textContent = text;
    }

    function hideBar() {
        const bar = document.getElementById('mnx-calling-bar');
        if (bar) bar.classList.remove('mnx-calling-show');
        if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    }

    // ------------------------------------------------------------
    // TOAST — small transient message
    // ------------------------------------------------------------
    function showToast(message, isError) {
        let toast = document.getElementById('mnx-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'mnx-toast';
            toast.className = 'mnx-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.toggle('mnx-toast-error', !!isError);
        toast.classList.add('mnx-toast-show');
        clearTimeout(toast._hideTimer);
        toast._hideTimer = setTimeout(() => {
            toast.classList.remove('mnx-toast-show');
        }, TOAST_TIMEOUT_MS);
    }

    // ------------------------------------------------------------
    // START CALL
    // ------------------------------------------------------------
    async function startCall(userId, callType) {
        if (!userId) return;
        const csrf = getCookie('csrftoken') || '';

        try {
            const res = await fetch(`/call/start/${userId}/${callType}/`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json',
                    'X-CSRFToken': csrf,
                },
            });

            // Non-JSON errors (e.g. server error page)
            const contentType = res.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
                showToast('Server did not respond correctly. Reload the page.', true);
                return;
            }

            const data = await res.json();

            if (!res.ok || data.ok === false) {
                const reason = data.reason || 'error';
                const message =
                    reason === 'busy' ? 'User is currently in another call. Try again in a minute.' :
                    reason === 'self' ? "You can't call yourself." :
                    reason === 'blocked' ? "You can't call this user." :
                    reason === 'forbidden' ? "You're not allowed to call this user." :
                    'Unable to start call.';
                showToast(message, true);
                return;
            }

            currentCallId = data.call_id;
            showBar('Calling…');
            pollStatus();

        } catch (e) {
            showToast('Network error. Check your connection.', true);
        }
    }

    // ------------------------------------------------------------
    // POLL CALL STATUS
    // ------------------------------------------------------------
    async function pollStatus() {
        if (!currentCallId) return;
        try {
            const res = await fetch(`/call/${currentCallId}/status/`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) {
                hideBar();
                currentCallId = null;
                return;
            }
            const data = await res.json();

            if (data.status === 'active') {
                window.location.href = `/call/${currentCallId}/`;
                return;
            }
            if (data.status === 'rejected') {
                setBarText('Call declined');
                setTimeout(() => {
                    hideBar();
                    currentCallId = null;
                }, 1500);
                return;
            }
            if (data.status === 'missed') {
                setBarText('No answer');
                setTimeout(() => {
                    hideBar();
                    currentCallId = null;
                }, 1500);
                return;
            }
            if (data.status === 'ended' || data.status === 'missing') {
                hideBar();
                currentCallId = null;
                return;
            }
        } catch (e) { /* ignore, retry */ }

        pollTimer = setTimeout(pollStatus, POLL_MS);
    }

    // ------------------------------------------------------------
    // CANCEL CALL
    // ------------------------------------------------------------
    async function cancelCall() {
        if (!currentCallId) { hideBar(); return; }
        const csrf = getCookie('csrftoken') || '';
        try {
            await fetch(`/call/${currentCallId}/cancel/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
            });
        } catch (e) { /* ignore */ }
        currentCallId = null;
        hideBar();
    }

    // ------------------------------------------------------------
    // UTILITIES
    // ------------------------------------------------------------
    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[2]) : '';
    }

    // ------------------------------------------------------------
    // HOOK .mnx-call-start CLICKS
    // data-user-id, data-type (voice|video)
    // ------------------------------------------------------------
    document.addEventListener('click', function (e) {
        const el = e.target.closest('.mnx-call-start');
        if (!el) return;
        e.preventDefault();
        const userId = el.getAttribute('data-user-id');
        const type = el.getAttribute('data-type') || 'video';
        startCall(userId, type);
    });
})();