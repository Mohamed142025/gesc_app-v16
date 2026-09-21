(() => {
	const counterClass = "gesc-app-notification-count";
	let notificationCount = 0;

	function getNotificationTargets() {
		return $(
			".standard-items-sections .sidebar-notification .sidebar-item-icon, " +
			".desktop-notifications .dropdown-notifications > .nav-link"
		);
	}

	function renderCount(count) {
		getNotificationTargets().each((_, element) => {
			const icon = $(element);
			let badge = icon.find(`.${counterClass}`);
			if (!badge.length) {
				badge = $(`<span class="${counterClass}" aria-label="${__("Unread notifications")}"></span>`);
				icon.append(badge);
			}
			badge.text(count > 99 ? "99+" : count).show();
		});
	}

	function refreshCount() {
		frappe.call({
			method: "gesc_app.gesc_app.notification_handler.get_unread_notification_count",
		}).then((response) => {
			notificationCount = Number(response.message) || 0;
			renderCount(notificationCount);
		});
	}

	function initialize() {
		refreshCount();
		setTimeout(refreshCount, 1000);
		setTimeout(refreshCount, 2500);
		let targetCount = getNotificationTargets().length;
		const targetPoll = setInterval(() => {
			const nextTargetCount = getNotificationTargets().length;
			if (nextTargetCount !== targetCount) {
				targetCount = nextTargetCount;
				renderCount(notificationCount);
			}
		}, 250);
		setTimeout(() => clearInterval(targetPoll), 10000);
		new MutationObserver(() => {
			const nextTargetCount = getNotificationTargets().length;
			if (nextTargetCount !== targetCount) {
				targetCount = nextTargetCount;
				refreshCount();
			}
		}).observe(document.body, {
			attributes: true,
			attributeFilter: ["class"],
			childList: true,
			subtree: true,
		});

		frappe.realtime.on("notification", refreshCount);
		frappe.realtime.on("indicator_hide", refreshCount);
		$(document).on("page-change", refreshCount);
	}

	$(initialize);
})();