/* global frappe */

(function () {
	"use strict";

	const WIDGET_ID = "sa-chatbot-root";
	const CHATBOT_NAME = "Scholarship Assitant";

	function shouldAttach() {
		// only website pages (not Desk)
		return !window.location.pathname.startsWith("/app");
	}

	function el(tag, attrs, children) {
		const node = document.createElement(tag);
		if (attrs) {
			for (const [k, v] of Object.entries(attrs)) {
				if (k === "class") node.className = v;
				else if (k === "text") node.textContent = v;
				else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
				else node.setAttribute(k, v);
			}
		}
		(children || []).forEach((c) => node.appendChild(c));
		return node;
	}

	function scrollToBottom(body) {
		body.scrollTop = body.scrollHeight;
	}

	function renderMessage(body, role, text, html) {
		const bubble = el("div", { class: "sa-bubble" });
		if (role === "bot" && html) bubble.innerHTML = html;
		else bubble.textContent = text || "";
		body.appendChild(el("div", { class: `sa-msg ${role === "user" ? "sa-user" : "sa-bot"}` }, [bubble]));
		scrollToBottom(body);
	}

	function setOpen(panel, open) {
		panel.classList.toggle("sa-open", !!open);
	}

	function callInitiateChat({ message, session_id }) {
		if (typeof frappe !== "undefined" && frappe.call) {
			return new Promise((resolve, reject) => {
				frappe.call({
					method: "usi.api.chat.initate_chat",
					args: { message, session_id, page: window.location.pathname },
					callback: (r) => resolve(r && r.message),
					error: (e) => reject(e),
				});
			});
		}

		return fetch("/api/method/usi.api.chat.initate_chat", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ message, session_id, page: window.location.pathname }),
		})
			.then((r) => r.json())
			.then((j) => j && j.message);
	}

	function init() {
		if (!shouldAttach()) return;
		if (document.getElementById(WIDGET_ID)) return;

		let session_id = null;

		const body = el("div", { class: "sa-body" });
		const input = el("textarea", { class: "sa-input", rows: "1", placeholder: "Ask about scholarships, eligibility, documents…" });
		const send = el("button", { class: "sa-send", type: "button", text: "Send" });
		const close = el("button", { class: "sa-close", type: "button", "aria-label": "Close", text: "✕" });

		const panel = el("div", { class: "sa-panel", role: "dialog", "aria-label": CHATBOT_NAME }, [
			el("div", { class: "sa-header" }, [
				el("div", { class: "sa-title" }, [
					el("strong", { text: CHATBOT_NAME }),
					el("span", { text: "Ask me anything about schemes" }),
				]),
				close,
			]),
			body,
			el("div", { class: "sa-footer" }, [el("div", { class: "sa-input-row" }, [input, send])]),
		]);

		const fab = el("button", { class: "sa-fab", type: "button", "aria-label": `Open ${CHATBOT_NAME}`, text: "Chat" });
		const root = el("div", { class: "sa-chatbot", id: WIDGET_ID }, [panel, fab]);

		document.body.appendChild(root);
		renderMessage(body, "bot", `Hi! I’m the ${CHATBOT_NAME}. How can I help you today?`);

		fab.addEventListener("click", () => setOpen(panel, !panel.classList.contains("sa-open")));
		close.addEventListener("click", () => setOpen(panel, false));

		function doSend() {
			const message = (input.value || "").trim();
			if (!message) return;
			input.value = "";
			send.disabled = true;

			renderMessage(body, "user", message);
			renderMessage(body, "bot", "…");

			callInitiateChat({ message, session_id })
				.then((payload) => {
					const reply = typeof payload === "string" ? payload : (payload && (payload.reply || payload.message)) || "";
					const reply_html = payload && payload.reply_html;
					const sid = payload && payload.session_id;
					if (sid) session_id = sid;
					body.removeChild(body.lastChild);
					renderMessage(body, "bot", reply || "Sorry — I didn’t get a response. Please try again.", reply_html);
				})
				.catch(() => {
					body.removeChild(body.lastChild);
					renderMessage(body, "bot", "Sorry — there was a problem contacting the server. Please try again.");
				})
				.finally(() => {
					send.disabled = false;
					input.focus();
				});
		}

		send.addEventListener("click", doSend);
		input.addEventListener("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				doSend();
			}
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();

