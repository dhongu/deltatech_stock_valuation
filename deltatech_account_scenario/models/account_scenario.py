# ©  2024 Deltatech
# See README.rst file on addons root folder for license details

import base64
import glob
import json
import logging
import os

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


class AccountScenario(models.Model):
    _name = "account.scenario"
    _description = "Test Scenario for Management Accounting"

    name = fields.Char(required=True)
    description = fields.Text()
    json_data = fields.Text(required=True, help="Raw JSON definition of the test scenario")
    mode = fields.Selection(
        [
            ("demo", "Generate Demo Data"),
            ("test", "Run and Validate"),
        ],
        default="test",
        required=True,
        help="demo = create data only; test = create data and validate account moves",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("executed", "Executed"),
            ("failed", "Failed"),
        ],
        default="draft",
    )
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    last_error = fields.Text(readonly=True)
    run_ids = fields.One2many("account.test.run", "scenario_id", string="Runs")
    run_count = fields.Integer(compute="_compute_run_count")

    def _compute_run_count(self):
        for rec in self:
            rec.run_count = len(rec.run_ids)

    def action_open_import_wizard(self):
        """Open the multi-file import wizard."""
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Import Scenarios"),
            "res_model": "account.scenario.import.wizard",
            "view_mode": "form",
            "target": "new",
        }

    def action_export_json(self):
        """Export current scenario as a downloadable JSON file."""
        self.ensure_one()
        try:
            data = json.loads(self.json_data)
        except Exception as e:
            raise UserError(self.env._("Invalid JSON: %s", e)) from e

        export_data = {
            "name": self.name,
            "mode": self.mode,
            "description": self.description or "",
        }
        export_data.update(data)

        raw = json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")
        encoded = base64.b64encode(raw).decode("utf-8")
        filename = (self.name or "scenario").replace(" ", "_") + ".json"

        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "datas": encoded,
                "mimetype": "application/json",
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def action_set_ready(self):
        for rec in self:
            try:
                json.loads(rec.json_data)
                rec.state = "ready"
                rec.last_error = False
            except Exception as e:
                raise UserError(self.env._("Invalid JSON: %s", e)) from e

    def action_execute_selected(self):
        """Run all selected scenarios (from list view action menu)."""
        for rec in self:
            rec.action_execute()

    def action_execute(self):
        self.ensure_one()
        try:
            scenario = json.loads(self.json_data)
        except Exception as e:
            raise UserError(self.env._("Invalid JSON: %s", e)) from e
        run = self.env["account.test.run"].create(
            {
                "scenario_id": self.id,
            }
        )
        try:
            result = run.execute(scenario)
            if result is False:
                self.state = "failed"
                self.last_error = run.error_message or self.env._("Execution failed")
            else:
                self.state = "executed"
                self.last_error = False
        except Exception as e:
            self.state = "failed"
            self.last_error = str(e)
            # nu trebuie sa fie afisata eroarea
            # raise UserError(self.env._("Execution failed: %s") % e)

    @api.model
    def load_demo_scenarios(self):
        """Load all JSON scenario files from data/scenarios/. Called from demo XML."""
        scenarios_dir = file_path("deltatech_account_scenario/data/scenarios")
        json_files = sorted(glob.glob(os.path.join(scenarios_dir, "**", "*.json"), recursive=True))
        for filepath in json_files:
            # Skip base_data — it is not a scenario, it is loaded automatically by the runner
            if os.path.basename(filepath) == "00_base_data.json":
                continue
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                _logger.warning("Could not load scenario file %s: %s", filepath, e)
                continue

            xml_id = data.get("id")
            name = data.get("name", os.path.basename(filepath))
            mode = data.get("mode", "test")
            description = data.get("description", "")
            json_data_dict = {
                "name": name,
                "lines": data.get("lines", []),
                "expected_account_moves": data.get("expected_account_moves", []),
            }
            if data.get("base_data_script"):
                json_data_dict["base_data_script"] = data["base_data_script"]
            json_data = json.dumps(
                json_data_dict,
                indent=2,
                ensure_ascii=False,
            )
            vals = {
                "name": name,
                "mode": mode,
                "description": description,
                "json_data": json_data,
                "state": "ready",
            }
            if xml_id:
                full_xml_id = f"deltatech_account_scenario.{xml_id}"
                existing = self.env.ref(full_xml_id, raise_if_not_found=False)
                if existing:
                    vals.pop("state")
                    existing.write(vals)
                    _logger.info("Updated demo scenario: %s", name)
                else:
                    record = self.env["account.scenario"].create(vals)
                    self.env["ir.model.data"].create(
                        {
                            "name": xml_id,
                            "module": "deltatech_account_scenario",
                            "model": "account.scenario",
                            "res_id": record.id,
                            "noupdate": True,
                        }
                    )
                    _logger.info("Created demo scenario: %s", name)
            else:
                self.env["account.scenario"].create(vals)
                _logger.info("Created demo scenario (no id): %s", name)

    @api.model
    def load_base_data(self):
        """Load and execute 00_base_data.json. Called from XML data file and by the runner."""
        records = self._get_base_data_records()
        _logger.info("Base data loaded: %d records", len(records))

    def _get_base_data_records(self, base_data_script=None):
        """Load base data JSON and return a records dict with shared partners, products, categories.
        If base_data_script is given, it is first looked up as an Odoo scenario by external ID
        (deltatech_account_scenario.<base_data_script>). If found, its json_data lines are executed.
        Otherwise it is loaded from data/scenarios/<base_data_script>.json (local file fallback).
        If no base_data_script is given, the default 00_base_data.json is used.
        """
        base_data = None

        if base_data_script:
            # 1. Caută scenariul în Odoo după external ID
            full_xml_id = f"deltatech_account_scenario.{base_data_script}"
            base_scenario = self.env.ref(full_xml_id, raise_if_not_found=False)
            if base_scenario:
                try:
                    base_data = json.loads(base_scenario.json_data)
                    _logger.info("Base data script '%s' loaded from Odoo scenario.", base_data_script)
                except Exception as e:
                    _logger.warning("Could not parse json_data for base scenario '%s': %s", base_data_script, e)

            if base_data is None:
                # 2. Fallback: fișier local
                # Încearcă cu extensie .json dacă nu e deja inclusă
                rel_name = base_data_script if base_data_script.endswith(".json") else f"{base_data_script}.json"
                rel_path = f"deltatech_account_scenario/data/scenarios/{rel_name}"
                try:
                    base_path = file_path(rel_path, filter_ext=(".json",))
                    with open(base_path, encoding="utf-8") as f:
                        base_data = json.load(f)
                    _logger.info("Base data script '%s' loaded from local file.", base_data_script)
                except Exception as e:
                    _logger.warning("Could not load base data script '%s' from file: %s", base_data_script, e)
                    base_data = {}
        else:
            rel_path = "deltatech_account_scenario/data/scenarios/00_base_data.json"
            base_path = file_path(rel_path, filter_ext=(".json",))
            with open(base_path, encoding="utf-8") as f:
                base_data = json.load(f)

        run = self.env["account.test.run"].new({})
        records = {}
        for step in base_data.get("lines", []):
            step = dict(step)
            step_type = step.get("step") or step.get("type")
            method_name = f"_run_step_{step_type.replace('-', '_')}"
            if hasattr(run, method_name):
                result = getattr(run, method_name)(step, records)
                if isinstance(result, dict):
                    records.update(result)
        return records

    def action_view_runs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Runs",
            "res_model": "account.test.run",
            "view_mode": "list,form",
            "domain": [("scenario_id", "=", self.id)],
        }
