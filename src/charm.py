#!/usr/bin/env python3
# Copyright 2022 Berkay Tekin Oz
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from ops.charm import CharmBase, RelationChangedEvent, RelationBrokenEvent
from ops.main import main
from ops.framework import StoredState
from ops.model import ActiveStatus, WaitingStatus

logger = logging.getLogger(__name__)


class SampleWorkloadCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(
            self.on.wordpress_pebble_ready, self._on_wordpress_pebble_ready
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fortune_action, self._on_fortune_action)
        self.framework.observe(
            self.on.mysql_relation_changed, self._on_mysql_relation_changed
        )
        self.framework.observe(
            self.on.mysql_relation_broken, self._on_mysql_relation_broken
        )
        self._stored.set_default(
            db_config={"name": "", "host": "", "password": "", "user": ""}
        )

    def _on_wordpress_pebble_ready(self, event):
        """Define and start a workload using the Pebble API.

        TEMPLATE-TODO: change this example to suit your needs.
        You'll need to specify the right entrypoint and environment
        configuration for your specific workload. Tip: you can see the
        standard entrypoint of an existing container using docker inspect

        Learn more about Pebble layers at https://github.com/canonical/pebble
        """
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
        # Define an initial Pebble layer configuration
        pebble_layer = self._wordpress_layer()
        # Add initial Pebble config layer using the Pebble API
        container.add_layer("wordpress", pebble_layer, combine=True)
        # Autostart any services that were defined with startup: enabled
        container.autostart()
        # Learn more about statuses in the SDK docs:
        # https://juju.is/docs/sdk/constructs#heading--statuses
        self.unit.status = ActiveStatus()

    def _wordpress_layer(self):
        return {
            "summary": "wordpress layer",
            "description": "pebble config layer for wordpress",
            "services": {
                "wordpress": {
                    "override": "replace",
                    "summary": "wordpress",
                    "command": "docker-entrypoint.sh apache2-foreground",
                    "startup": "enabled",
                    "environment": {
                        "WP_DEBUG": self.model.config["wp-debug"],
                        "WP_DATABASE_HOST": self._stored.db_config["host"],
                        "WP_DATABASE_USER": self._stored.db_config["user"],
                        "WP_DATABASE_PASSWORD": self._stored.db_config["password"],
                        "WP_DATABASE_NAME": self._stored.db_config["name"],
                    },
                }
            },
        }

    def _on_config_changed(self, _):
        """Handle the config-changed event"""
        # Get the gosherve container so we can configure/manipulate it
        container = self.unit.get_container("wordpress")
        # Create a new config layer
        layer = self._wordpress_layer()

        if container.can_connect():
            # Get the current config
            services = container.get_plan().to_dict().get("services", {})
            # Check if there are any changes to services
            if services != layer["services"]:
                # Changes were made, add the new layer
                container.add_layer("wordpress", layer, combine=True)
                logging.info("Added updated layer 'wordpress' to Pebble plan")
                # Restart it and report a new status to Juju
                container.restart("wordpress")
                logging.info("Restarted wordpress service")
            # All is well, set an ActiveStatus
            self.unit.status = ActiveStatus()
        else:
            self.unit.status = WaitingStatus("waiting for Pebble in workload container")

    def _on_mysql_relation_changed(self, event: RelationChangedEvent) -> None:

        if event.unit:
            logger.info(event.unit)
            logger.info(event.relation.data[event.unit])
            database = event.relation.data[event.unit].get("database")
            host = event.relation.data[event.unit].get("host")
            password = event.relation.data[event.unit].get("password")
            user = event.relation.data[event.unit].get("user")
            self._stored.db_config.update(
                {"name": database, "host": host, "password": password, "user": user}
            )

            logger.info("New database configuration {}".format(self._stored.db_config))

        self._on_config_changed(event)

    def _on_mysql_relation_broken(self, event: RelationBrokenEvent) -> None:
        # Remove the unit data from local state
        self._stored.db_config.update(
            {"name": "", "host": "", "password": "", "user": ""}
        )
        # Do something
        self._on_config_changed(event)

    def _on_fortune_action(self, event):
        """Just an example to show how to receive actions.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle actions, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the actions.py file.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            event.set_results(
                {"fortune": "A bug in the code is worth two in the documentation."}
            )


if __name__ == "__main__":
    main(SampleWorkloadCharm)
