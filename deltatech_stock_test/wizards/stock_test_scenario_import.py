# ©  2024 Deltatech
# See README.rst file on addons root folder for license details

import base64
import io
import json
import logging
import os
import zipfile

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockTestScenarioImportWizard(models.TransientModel):
    _name = "stock.test.scenario.import.wizard"
    _description = "Import Multiple JSON Scenarios"

    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="JSON / ZIP Files",
        help="Select one or more .json files or a .zip archive containing JSON scenario files",
    )

    def _process_scenario_data(self, data, source_name=""):
        """Create or update a scenario from a parsed JSON dict. Returns True if processed."""
        name = data.get("name", source_name or "Imported Scenario")
        mode = data.get("mode", "test")
        description = data.get("description", "")
        json_data_dict = {
            "name": name,
            "lines": data.get("lines", []),
            "expected_account_moves": data.get("expected_account_moves", []),
        }
        if data.get("base_data_script"):
            json_data_dict["base_data_script"] = data["base_data_script"]
        json_data = json.dumps(json_data_dict, indent=2, ensure_ascii=False)

        xml_id = data.get("id")
        vals = {
            "name": name,
            "mode": mode,
            "description": description,
            "json_data": json_data,
            "state": "ready",
        }
        if xml_id:
            full_xml_id = f"deltatech_stock_test.{xml_id}"
            existing = self.env.ref(full_xml_id, raise_if_not_found=False)
            if existing:
                vals.pop("state")
                existing.write(vals)
                _logger.info("Updated scenario: %s", name)
            else:
                record = self.env["stock.test.scenario"].create(vals)
                self.env["ir.model.data"].create(
                    {
                        "name": xml_id,
                        "module": "deltatech_stock_test",
                        "model": "stock.test.scenario",
                        "res_id": record.id,
                        "noupdate": True,
                    }
                )
                _logger.info("Created scenario: %s", name)
        else:
            self.env["stock.test.scenario"].create(vals)
            _logger.info("Created scenario (no id): %s", name)
        return True

    def action_import(self):
        if not self.attachment_ids:
            raise UserError(self.env._("Please select at least one file."))

        loaded = 0
        for attachment in self.attachment_ids:
            raw_bytes = base64.b64decode(attachment.datas)
            if attachment.name.endswith(".zip"):
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                        for entry in sorted(zf.namelist()):
                            if not entry.endswith(".json"):
                                continue
                            if os.path.basename(entry) == "00_base_data.json":
                                continue
                            try:
                                data = json.loads(zf.read(entry).decode("utf-8"))
                            except Exception as e:
                                _logger.warning("Could not parse %s: %s", entry, e)
                                continue
                            self._process_scenario_data(data, os.path.basename(entry))
                            loaded += 1
                except zipfile.BadZipFile as e:
                    raise UserError(self.env._("Invalid ZIP file: %s", e)) from e
            elif attachment.name.endswith(".json"):
                try:
                    data = json.loads(raw_bytes.decode("utf-8"))
                except Exception as e:
                    _logger.warning("Could not parse %s: %s", attachment.name, e)
                    continue
                self._process_scenario_data(data, attachment.name)
                loaded += 1
            else:
                _logger.warning("Skipping unsupported file: %s", attachment.name)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Scenarios Loaded"),
                "message": self.env._("%d scenario(s) loaded.", loaded),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
