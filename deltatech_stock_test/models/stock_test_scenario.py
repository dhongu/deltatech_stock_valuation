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


class StockTestScenario(models.Model):
    _name = "stock.test.scenario"
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
    run_ids = fields.One2many("stock.test.run", "scenario_id", string="Runs")
    run_count = fields.Integer(compute="_compute_run_count")
    import_file = fields.Binary(string="Import JSON File", attachment=False, store=False)
    import_filename = fields.Char(string="Filename", store=False)

    def _compute_run_count(self):
        for rec in self:
            rec.run_count = len(rec.run_ids)

    def action_import_json(self):
        """Import scenario from uploaded JSON file."""
        self.ensure_one()
        if not self.import_file:
            raise UserError(self.env._("Please upload a JSON file first."))
        try:
            raw = base64.b64decode(self.import_file).decode("utf-8")
            data = json.loads(raw)
        except Exception as e:
            raise UserError(self.env._("Invalid JSON file: %s") % e)

        name = data.get("name", self.import_filename or "Imported Scenario")
        mode = data.get("mode", "test")
        description = data.get("description", "")
        json_data = json.dumps(
            {
                "name": name,
                "lines": data.get("lines", []),
                "expected_account_moves": data.get("expected_account_moves", []),
            },
            indent=2,
            ensure_ascii=False,
        )
        self.write(
            {
                "name": name,
                "mode": mode,
                "description": description,
                "json_data": json_data,
                "state": "ready",
                "import_file": False,
                "import_filename": False,
            }
        )

    def action_set_ready(self):
        for rec in self:
            try:
                json.loads(rec.json_data)
                rec.state = "ready"
                rec.last_error = False
            except Exception as e:
                raise UserError(self.env._("Invalid JSON: %s") % e)

    def action_execute(self):
        self.ensure_one()
        try:
            scenario = json.loads(self.json_data)
        except Exception as e:
            raise UserError(self.env._("Invalid JSON: %s") % e)
        run = self.env["stock.test.run"].create(
            {
                "scenario_id": self.id,
            }
        )
        try:
            run.execute(scenario)
            self.state = "executed"
            self.last_error = False
        except Exception as e:
            self.state = "failed"
            self.last_error = str(e)
            raise UserError(self.env._("Execution failed: %s") % e)

    @api.model
    def load_demo_scenarios(self):
        """Load all JSON scenario files from data/scenarios/. Called from demo XML."""
        scenarios_dir = file_path("deltatech_stock_test/data/scenarios")
        json_files = sorted(glob.glob(os.path.join(scenarios_dir, "**", "*.json"), recursive=True))
        for filepath in json_files:
            # Skip base_data — it is not a scenario, it is loaded automatically by the runner
            if os.path.basename(filepath) == "00_base_data.json":
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                _logger.warning("Could not load scenario file %s: %s", filepath, e)
                continue

            xml_id = data.get("id")
            name = data.get("name", os.path.basename(filepath))
            mode = data.get("mode", "test")
            description = data.get("description", "")
            json_data = json.dumps(
                {
                    "name": name,
                    "lines": data.get("lines", []),
                    "expected_account_moves": data.get("expected_account_moves", []),
                },
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
                full_xml_id = "deltatech_stock_test.%s" % xml_id
                existing = self.env.ref(full_xml_id, raise_if_not_found=False)
                if existing:
                    existing.write(vals)
                    _logger.info("Updated demo scenario: %s", name)
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
                    _logger.info("Created demo scenario: %s", name)
            else:
                self.env["stock.test.scenario"].create(vals)
                _logger.info("Created demo scenario (no id): %s", name)

    @api.model
    def load_base_data(self):
        """Load and execute 00_base_data.json. Called from XML data file and by the runner."""
        records = self._get_base_data_records()
        _logger.info("Base data loaded: %d records", len(records))

    def _get_base_data_records(self):
        """Load 00_base_data.json and return a records dict with shared partners, products, categories."""
        base_path = file_path("deltatech_stock_test/data/scenarios/00_base_data.json", filter_ext=(".json",))
        with open(base_path, "r", encoding="utf-8") as f:
            base_data = json.load(f)
        run = self.env["stock.test.run"].new({})
        records = {}
        for step in base_data.get("lines", []):
            step = dict(step)
            step_type = step.get("step") or step.get("type")
            method_name = "_run_step_%s" % step_type.replace("-", "_")
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
            "res_model": "stock.test.run",
            "view_mode": "list,form",
            "domain": [("scenario_id", "=", self.id)],
        }
