// ============================================================
// MENNTRIX NOTIFICATIONS — unread badge polling + push subscribe
// ============================================================

(function () {
    'use strict';

    const POLL_MS = 30000; // 30s
    const PROMPT_SHOWN_KEY = 'mnx_push_prompt_shown';

    // ------------------------------------------------------------
    // Unread badge polling
    // ------------------------------------------------------------
    async function pollUnread() {
        try {
            const res = await fetch('/notifications/count/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) return;
            const data = await res.json();
            const badge = document.getElementById('mnxBellBadge');
            if (!badge) return;
            if (data.count > 0) {
                badge.textContent = data.count > 99 ? '99+' : data.count;
                badge.style.display = 'inline-flex';
            } else {
                badge.style.display = 'none';
            }
        } catch (e) { /* ignore */ }
    }

    // ------------------------------------------------------------
    // Push subscription helpers
    // ------------------------------------------------------------
    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
        return outputArray;
    }

    async function getPublicKey() {
        try {
            const res = await fetch('/push/public-key/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) return null;
            const data = await res.json();
            return data.publicKey || null;
        } catch (e) { return null; }
    }

    async function subscribePush() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.warn('Push not supported');
            return false;
        }

        try {
            const reg = await navigator.serviceWorker.ready;
            const perm = await Notification.requestPermission();
            if (perm !== 'granted') return false;

            const publicKey = await getPublicKey();
            if (!publicKey) {
                console.warn('No VAPID public key configured');
                return false;
            }

            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey),
            });

            const csrf = getCookie('csrftoken') || '';
            await fetch('/push/subscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrf,
                },
                body: JSON.stringify(sub.toJSON()),
            });

            return true;
        } catch (e) {
            console.warn('Push subscribe failed', e);
            return false;
        }
    }

    function getCookie(name) {
        const m = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[2]) : '';
    }

    // ------------------------------------------------------------
    // Push permission banner (once per browser)
    // ------------------------------------------------------------
    function showPromptBanner() {
        if (localStorage.getItem(PROMPT_SHOWN_KEY)) return;
        if (!('Notification' in window)) return;
        if (Notification.permission === 'granted' || Notification.permission === 'denied') return;

        const banner = document.createElement('div');
        banner.className = 'mnx-push-banner';
        banner.innerHTML = `
            <div class="mnx-push-banner-inner">
                <span>Enable device notifications for MENNTRIX?</span>
                <div class="mnx-push-banner-actions">
                    <button type="button" id="mnx-push-enable" class="mnx-btn mnx-btn-primary">ENABLE</button>
                    <button type="button" id="mnx-push-later" class="mnx-btn">NOT NOW</button>
                </div>
            </div>
        `;
        document.body.appendChild(banner);
        setTimeout(() => banner.classList.add('mnx-push-banner-show'), 50);

        document.getElementById('mnx-push-enable').onclick = async () => {
            const ok = await subscribePush();
            banner.remove();
            localStorage.setItem(PROMPT_SHOWN_KEY, '1');
        };
        document.getElementById('mnx-push-later').onclick = () => {
            localStorage.setItem(PROMPT_SHOWN_KEY, '1');
            banner.classList.remove('mnx-push-banner-show');
            setTimeout(() => banner.remove(), 300);
        };
    }

    // ------------------------------------------------------------
    // Service worker registration
    // ------------------------------------------------------------
    async function registerSW() {
        if (!('serviceWorker' in navigator)) return;
        try {
            await navigator.serviceWorker.register('/menntrix-sw.js', { scope: '/' });
        } catch (e) {
            console.warn('SW register failed', e);
        }
    }

    // ------------------------------------------------------------
    // Start
    // ------------------------------------------------------------
    function start() {
        pollUnread();
        setInterval(pollUnread, POLL_MS);
        registerSW().then(() => {
            setTimeout(showPromptBanner, 4000);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
})();