
import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from awscrt import io, mqtt, auth
from awsiot import mqtt_connection_builder
from main import run_once  

load_dotenv()

ENDPOINT = os.getenv("ENDPOINT")
REGION = os.getenv("REGION", "us-east-2")
CLIENT_ID = os.getenv("NBA_CLIENT_ID", "nba-publisher-ec2")
TOPIC = os.getenv("NBA_TOPIC", "nba/live/scores")

POLL_INTERVAL = 180  # 3 minutes, same as NFL

if not ENDPOINT:
    raise RuntimeError("ENDPOINT is not set in environment (.env).")


#MQTT SETUP 

event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
    endpoint=ENDPOINT,
    client_id=CLIENT_ID,
    region=REGION,
    credentials_provider=auth.AwsCredentialsProvider.new_default_chain(client_bootstrap),
    clean_session=False,
    keep_alive_secs=30,
)

print(f"Connecting to {ENDPOINT} with client ID {CLIENT_ID}...")
mqtt_connection.connect().result()
print("✅ Connected to AWS IoT (NBA publisher)!")

last_data = None

try:
    while True:
        new_data = run_once()

        within_hours = new_data.get("within_polling_hours", True)

        if not within_hours:
            print(
                f"🕒 Outside polling window at "
                f"{datetime.now(ZoneInfo('America/Chicago'))}, skipping publish."
            )
        else:
            if new_data != last_data:
                mqtt_connection.publish(
                    topic=TOPIC,
                    payload=json.dumps(new_data, default=str, indent=2),
                    qos=mqtt.QoS.AT_LEAST_ONCE,
                )
                print(
                    f"📡 [NBA] Published updated data to {TOPIC} "
                    f"at {datetime.now(ZoneInfo('America/Chicago'))}"
                )
                last_data = new_data
            else:
                print(
                    f"⏸ [NBA] No change in data at "
                    f"{datetime.now(ZoneInfo('America/Chicago'))}"
                )

        time.sleep(POLL_INTERVAL)

except KeyboardInterrupt:
    print("Stopping NBA publisher...")

finally:
    mqtt_connection.disconnect().result()
    print("🔌 Disconnected from AWS IoT (NBA)")
