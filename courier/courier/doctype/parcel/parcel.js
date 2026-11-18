frappe.ui.form.on("Parcel", {
	refresh(frm) {
		const status = frm.doc.status;

		const add = (label, action) => {
			frm.add_custom_button(
				label,
				() => {
					frappe.prompt(
						{ fieldname: "reason", fieldtype: "Small Text", label: "Reason" },
						(values) => {
							frappe.call({
								method: "courier.api.ops_action",
								args: { name: frm.doc.name, action: action, reason: values.reason },
								callback: () => frm.reload_doc(),
							});
						},
						label
					);
				},
				"Exception"
			);
		};

		const out = ["Out for Delivery", "Return Out for Delivery"];
		const hubs = ["In at Origin Hub", "In at Destination Hub", "Return In at Pickup Hub", "Return In at Drop Hub"];

		if (out.includes(status)) add("Mark Failed Delivery", "fail_delivery");
		if (hubs.includes(status)) add("Put On Hold", "hold");
		if (["Delivery Failed", "On Hold"].includes(status)) add("Resume", "resume");
	},
});
