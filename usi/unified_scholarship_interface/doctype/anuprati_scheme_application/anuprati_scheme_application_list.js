frappe.listview_settings["Anuprati Scheme Application"] = {
    onload(listview) {
        listview.page.add_inner_button("Run Allotment", () => {
            frappe.confirm(
                "Are you sure you want to run allotment?",
                () => {
                    frappe.call({
                        method: "usi.services.anuprati_scheme_manager.run_allotment",
                        freeze: true,
                        freeze_message: "Running allotments, please wait...",
                        callback(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: r.message,
                                    indicator: "green"
                                });
                                listview.refresh();
                            }
                        }
                    });
                }
            );
        });
    }
};