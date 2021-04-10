"""Constants for the Loop Energy Sensor integration."""

DOMAIN = "loop"
SENSOR_POWER = "power_usage"
SENSOR_PHANTOM = "phantom_load"
SCAN_INTERVAL = 5
SIGNAL_NAME_PREFIX = f"signal_{DOMAIN}"
MANUFACTURER = "Loop"

ICON_POWER_USAGE = "mdi:power-plug"
ICON_PHANTOM_LOAD = "mdi:ghost"
NAME_POWER_USAGE = "Power Usage"
NAME_PHANTOM_LOAD = "Phantom Load"

PHANTOM_ENDPOINT = (
    "https://yfp2dgq9mk.execute-api.eu-west-1.amazonaws.com/Test/usage/phantom_load"
)
LIVE_ENDPOINT = "https://yfp2dgq9mk.execute-api.eu-west-1.amazonaws.com/Test/usage/live"
COGNITO_ENDPOINT = "https://cognito-idp.eu-west-1.amazonaws.com/"
CLIENT_ID = "7e8i2f7mffi61b3vs9n35aocmt"