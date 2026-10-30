"""Publish snapshots to AWS IoT Core over MQTT. Needs: pip install awsiotsdk"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


class AwsIotSink:
    name = "aws_iot"

    def __init__(self, settings):
        from awscrt import auth, io, mqtt            # lazy imports
        from awsiot import mqtt_connection_builder

        if not settings.aws_endpoint:
            raise RuntimeError("ENDPOINT is not set (AWS IoT endpoint). Check your .env")

        self._mqtt = mqtt
        self._topic = settings.aws_topic
        loop = io.EventLoopGroup(1)
        bootstrap = io.ClientBootstrap(loop, io.DefaultHostResolver(loop))
        self._conn = mqtt_connection_builder.websockets_with_default_aws_signing(
            endpoint=settings.aws_endpoint,
            client_id=settings.aws_client_id,
            region=settings.aws_region,
            credentials_provider=auth.AwsCredentialsProvider.new_default_chain(bootstrap),
            clean_session=False,
            keep_alive_secs=30,
            on_connection_interrupted=lambda connection, error, **kw: log.warning("IoT connection interrupted: %s", error),
            on_connection_resumed=lambda connection, return_code, session_present, **kw: log.info("IoT connection resumed"),
        )
        log.info("Connecting to AWS IoT %s as %s ...", settings.aws_endpoint, settings.aws_client_id)
        self._conn.connect().result(timeout=30)
        log.info("Connected to AWS IoT")

    def publish(self, snapshot) -> None:
        payload = json.dumps(snapshot.payload(), separators=(",", ":"), default=str)
        # retain=True: a display that powers on later immediately gets the last known slate.
        # (Requires the iot:RetainPublish permission on the publisher's IAM policy.)
        future, _ = self._conn.publish(
            self._topic, payload, self._mqtt.QoS.AT_LEAST_ONCE, retain=True
        )
        future.result(timeout=10)
        log.info("Published %d games to %s (%d bytes)", len(snapshot.games), self._topic, len(payload))

    def close(self) -> None:
        self._conn.disconnect().result(timeout=10)
        log.info("Disconnected from AWS IoT")
