// ============================================================
// MENNTRIX INCOMING CALL LISTENER
// Opens a WebSocket to /ws/listener/, shows a floating card
// on any page when a call comes in. Plays ringtone.
// ============================================================

(function () {
    'use strict';

    const AUTO_DISMISS_MS = 30000; // 30s
    const RECONNECT_MS = 5000;

    let ws = null;
    let ringtone = null;
    let dismissTimer = null;
    let currentCall = null;

    // ------------------------------------------------------------
    // UI — floating card
    // ------------------------------------------------------------
    function ensureCard() {
        let card = document.getElementById('mnx-incoming-call');
        if (card) return card;

        card = document.createElement('div');
        card.id = 'mnx-incoming-call';
        card.className = 'mnx-incoming-call';
        card.innerHTML = `
            <div class="mnx-incoming-inner">
                <div class="mnx-incoming-avatar" id="mnx-incoming-avatar"></div>
                <div class="mnx-incoming-info">
                    <div class="mnx-incoming-label">Incoming call</div>
                    <div class="mnx-incoming-name" id="mnx-incoming-name">—</div>
                    <div class="mnx-incoming-type" id="mnx-incoming-type">—</div>
                </div>
                <div class="mnx-incoming-actions">
                    <button type="button" class="mnx-incoming-btn mnx-incoming-accept" id="mnx-incoming-accept">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                        </svg>
                        <span>ACCEPT</span>
                    </button>
                    <button type="button" class="mnx-incoming-btn mnx-incoming-reject" id="mnx-incoming-reject">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"/>
                            <line x1="9" y1="9" x2="15" y2="15"/>
                            <line x1="15" y1="9" x2="9" y2="15"/>
                        </svg>
                        <span>REJECT</span>
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(card);
        return card;
    }

    function showCard(call) {
        const card = ensureCard();
        currentCall = call;

        const avatarEl = card.querySelector('#mnx-incoming-avatar');
        const nameEl = card.querySelector('#mnx-incoming-name');
        const typeEl = card.querySelector('#mnx-incoming-type');

        nameEl.textContent = call.caller_name || call.caller_username || 'Unknown caller';
        typeEl.textContent = (call.call_type === 'video' ? 'Video call' : 'Voice call');

        if (call.caller_avatar) {
            avatarEl.innerHTML = `<img src="/media/profile_pictures/${call.caller_avatar}" alt="">`;
        } else {
            const initial = (call.caller_name || call.caller_username || '?').trim().charAt(0).toUpperCase();
            avatarEl.innerHTML = `<span>${initial}</span>`;
        }

        card.classList.add('mnx-incoming-show');

        // Wiring
        card.querySelector('#mnx-incoming-accept').onclick = () => {
            window.location.href = `/call/${call.call_id}/accept/`;
        };
        card.querySelector('#mnx-incoming-reject').onclick = () => {
            fetch(`/call/${call.call_id}/reject/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            }).finally(() => hideCard());
        };

        // Auto-dismiss after 30s
        dismissTimer = setTimeout(() => {
            fetch(`/call/${call.call_id}/reject/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    'X-Requested-With': 'XMLHttpRequest',
                },
            }).finally(() => hideCard());
        }, AUTO_DISMISS_MS);

        // Ring
        playRingtone();
    }

    function hideCard() {
        const card = document.getElementById('mnx-incoming-call');
        if (card) card.classList.remove('mnx-incoming-show');
        currentCall = null;
        if (dismissTimer) { clearTimeout(dismissTimer); dismissTimer = null; }
        stopRingtone();
    }

    // ------------------------------------------------------------
    // RINGTONE
    // ------------------------------------------------------------
    function playRingtone() {
        try {
            if (!ringtone) {
                ringtone = new Audio('/static/audio/ringtone.mp3');
                ringtone.loop = true;
                ringtone.volume = 0.6;
            }
            const p = ringtone.play();
            if (p && p.catch) p.catch(() => {/* autoplay blocked */});
        } catch (e) { /* silent */ }
    }

    function stopRingtone() {
        if (ringtone) {
            try { ringtone.pause(); ringtone.currentTime = 0; } catch (e) {}
        }
    }

    // ------------------------------------------------------------
    // WEBSOCKET
    // ------------------------------------------------------------
    function connect() {
        const wsScheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${wsScheme}://${window.location.host}/ws/listener/`;

        try {
            ws = new WebSocket(url);
        } catch (e) {
            setTimeout(connect, RECONNECT_MS);
            return;
        }

        ws.onmessage = (evt) => {
            let data;
            try { data = JSON.parse(evt.data); } catch (e) { return; }

            switch (data.type) {
                case 'incoming_call':
                    showCard(data);
                    break;
                case 'call_cancelled':
                    if (currentCall && currentCall.call_id === data.call_id) {
                        hideCard();
                    }
                    break;
                case 'call_accepted':
                    // Caller side: if they are waiting on the ringing bar, this is handled by callinit.js
                    break;
                case 'call_rejected':
                    // Caller side: handled by callinit.js
                    break;
                case 'call_ended':
                    // If we are currently IN the call room, instantly redirect to dashboard
                    if (window.location.pathname.includes('/call/')) {
                        window.location.href = '/dashboard/';
                    } else {
                        // Otherwise just clear any incoming call card
                        hideCard();
                    }
                    break;
            }
        };

        ws.onclose = () => {
            setTimeout(connect, RECONNECT_MS);
        };
        ws.onerror = () => { /* let onclose handle retry */ };
    }

    // ------------------------------------------------------------
    // CSRF helper
    // ------------------------------------------------------------
    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[2]) : '';
    }

    // ------------------------------------------------------------
    // Start
    // ------------------------------------------------------------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', connect);
    } else {
        connect();
    }
})();