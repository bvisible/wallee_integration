# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WalleeLocation(Document):
    """Wallee Location DocType for managing terminal locations."""

    def validate(self):
        """Validate the location document."""
        pass

    def on_trash(self):
        """Handle deletion - check for linked terminals."""
        linked_terminals = frappe.get_all(
            "Wallee Payment Terminal",
            filters={"wallee_location": self.name},
            pluck="name"
        )
        if linked_terminals:
            frappe.throw(
                _("Cannot delete location. It is linked to terminals: {0}").format(
                    ", ".join(linked_terminals)
                )
            )


def get_active_locations():
    """Get all active locations."""
    return frappe.get_all(
        "Wallee Location",
        filters={"is_active": 1},
        fields=["name", "location_name", "city", "country"]
    )
