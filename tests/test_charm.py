# Copyright 2022 Berkay Tekin Oz
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest
from unittest.mock import Mock

from charm import SampleWorkloadCharm
from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(SampleWorkloadCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()

    def test_config_changed(self):
        self.assertEqual(self.harness.charm.model.config["wp-debug"], "")
        self.harness.update_config({"wp-debug": "1"})
        self.assertEqual(self.harness.charm.model.config["wp-debug"], "1")

    def test_action(self):
        # the harness doesn't (yet!) help much with actions themselves
        action_event = Mock(params={"fail": ""})
        self.harness.charm._on_fortune_action(action_event)

        self.assertTrue(action_event.set_results.called)

    def test_action_fail(self):
        action_event = Mock(params={"fail": "fail this"})
        self.harness.charm._on_fortune_action(action_event)

        self.assertEqual(action_event.fail.call_args, [("fail this",)])

    def test_wordpress_pebble_ready(self):
        # Check the initial Pebble plan is empty
        initial_plan = self.harness.get_container_pebble_plan("wordpress")
        self.assertEqual(initial_plan.to_yaml(), "{}\n")
        # Expected plan after Pebble ready with default config
        expected_plan = {
            "services": {
                "wordpress": {
                    "override": "replace",
                    "summary": "wordpress",
                    "command": "docker-entrypoint.sh apache2-foreground",
                    "startup": "enabled",
                    "environment": {
                        "WP_DEBUG": self.harness.charm.model.config["wp-debug"],
                        "WP_DATABASE_HOST": self.harness.charm._stored.db_config["host"],
                        "WP_DATABASE_USER": self.harness.charm._stored.db_config["user"],
                        "WP_DATABASE_PASSWORD": self.harness.charm._stored.db_config[
                            "password"
                        ],
                        "WP_DATABASE_NAME": self.harness.charm._stored.db_config["name"],
                    },
                }
            },
        }
        # Get the wordpress container from the model
        container = self.harness.model.unit.get_container("wordpress")
        # Emit the PebbleReadyEvent carrying the wordpress container
        self.harness.charm.on.wordpress_pebble_ready.emit(container)
        # Get the plan now we've run PebbleReady
        updated_plan = self.harness.get_container_pebble_plan("wordpress").to_dict()
        # Check we've got the plan we expected
        self.assertEqual(expected_plan, updated_plan)
        # Check the service was started
        service = self.harness.model.unit.get_container("wordpress").get_service(
            "wordpress"
        )
        self.assertTrue(service.is_running())
        # Ensure we set an ActiveStatus with no message
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())
