# This program is used to get AWS CLI credentials from kion and
# save them to your aws configuration. It assumes you are already
# connected to zscaler, and will likely fail in strange and
# unusual ways if you aren't. Ideally, you would run this from a
# cron/otherwise scheduled job to keep things updated.
import datetime
import json
import logging
import logging.handlers
import os
import re
import shutil
import subprocess  # nosec: B404 this is all trusted inputs
import sys
import time
from configparser import ConfigParser

import click
from click.core import ParameterSource as Source


def creds_need_update(creds_file_path: str, profile_name: str) -> bool:
    """Inspect the credentials we currently have to see if they
    really need updated.
    """
    logging.info(f"Checking {creds_file_path} to see if update is necessary")
    config = ConfigParser()
    config.read(creds_file_path)

    if profile_name not in config.sections():
        logging.debug(f"Profile [{profile_name}] does not exist, forcing update.")
        return True

    expiration = config[profile_name].get("expiration")
    if not expiration:
        logging.debug(f"No expiration date found for [{profile_name}], forcing update.")
        return True

    expiration_time = datetime.datetime.fromisoformat(expiration)
    now = datetime.datetime.now(datetime.UTC)
    logging.debug(f"Expiration={expiration_time.utctimetuple()}")
    logging.debug(f"Now={now.utctimetuple()}")
    if expiration_time <= (now - datetime.timedelta(minutes=10)):
        # Assume we're running no less than every 10 minutes
        logging.debug(f"Credentials for [{profile_name}] expire in under 10 minutes. Updating.")
        return True

    logging.debug(f"Credentials for [{profile_name}] are still good for at least 10 minutes. Not updating.")
    return False


def replace_kion_yaml(kion_yaml_path: str) -> None:
    """Copy our template kion cli config to the blessed
    kion location.
    """
    destination_yaml = os.path.join(os.getenv("HOME"), ".kion.yml")  # kion cli is inflexible
    if kion_yaml_path == destination_yaml:
        logging.debug("Kion yaml is sourced from the expected location, not copying.")
        return

    logging.debug(f"Copying {kion_yaml_path} -> {destination_yaml}")
    shutil.copyfile(kion_yaml_path, destination_yaml)


def update_aws_credentials(creds_file_path: str, profile_name: str, aws_creds: dict[str, str]) -> None:
    """Given the new access key, secret key, and session token, save
    them for the named profile in the file indicated.
    """
    logging.info(f"Updating credentials in {creds_file_path}")
    # Initialize ConfigParser and read the credentials file
    config = ConfigParser()
    config.read(creds_file_path)

    # Ensure the profile exists in the credentials file, create it if missing
    if profile_name not in config.sections():
        logging.debug(f"Adding section {profile_name}")
        config.add_section(profile_name)

    # Update the profile with new credentials
    config[profile_name]["aws_access_key_id"] = aws_creds["AccessKeyId"]
    config[profile_name]["aws_secret_access_key"] = aws_creds["SecretAccessKey"]
    config[profile_name]["aws_session_token"] = aws_creds["SessionToken"]
    config[profile_name]["expiration"] = aws_creds["Expiration"]

    # Write the updated configuration back to the file
    with open(creds_file_path, "w") as creds_file:
        config.write(creds_file)

    logging.info(f"Credentials for profile [{profile_name}] updated successfully.")


def get_new_aws_credentials(favourite: str) -> dict[str, str]:
    """Retrieve new AWS CLI credentials from kion using the CLI."""
    logging.info("Retrieving AWS credentials from kion")
    json_output = subprocess.check_output(["kion", "favorite", "--credential-process", favourite])
    logging.debug(f"New credentials: {json_output}")
    return json.loads(json_output)


@click.command()
@click.version_option()
@click.option(
    "--credentials",
    help="Location of AWS Credentials file",
    default=os.path.join(os.getenv("HOME"), ".aws", "credentials"),
    show_default=True,
)
@click.option(
    "--config",
    help="Path of configuration file",
    default=os.path.join(os.getenv("HOME"), ".config", "aws-token-updater.ini"),
    show_default=True,
)
@click.option(
    "--kion-yaml",
    help="Path of kion configuration file",
    default=os.path.join(os.getenv("HOME"), ".config", "kion.yml"),
    show_default=True,
)
@click.option("--profile", help="Name of AWS profile to update")
@click.option("--favourite/--favorite", help="Name of kion favourite to use")
@click.option(
    "--log",
    help="Path of log file",
    default=os.path.join(os.getenv("HOME"), ".log", "kion-auth.log"),
    show_default=True,
)
@click.option("--debug", is_flag=True, help="Print extra logging")
@click.pass_context
def cli(ctx, credentials, config, kion_yaml, profile, favourite, log, debug):
    # Read configuration from the file if it exists, otherwise start
    # with an empty configuration and hope the user used the CLI args
    # Configuration prefers the CLI arguments if given, otherwise it
    # takes information from the config file.
    if os.path.exists(config):
        c = ConfigParser()
        c.read(config)
        cfg = c["aws_token_updater"]
    else:
        cfg = {}

    # We only want to override the log destination from the config
    # file if the user explicitly passed it in from the CLI.
    if ctx.get_parameter_source("log") == Source.DEFAULT and cfg.get("log"):
        log = cfg.get("log")

    if log == "stdout":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.handlers.RotatingFileHandler(log, backupCount=1, maxBytes=1024 * 1024)

    log_level = logging.INFO
    if debug:
        log_level = logging.DEBUG
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=log_level,
        handlers=[handler],
    )

    if not profile:
        profile = cfg.get("profile")

    if not favourite:
        favourite = cfg.get("favourite")

    # Just like the log destination file, we only want to override
    # what came in from the CLI args if what came in was the default
    if ctx.get_parameter_source("credentials") == Source.DEFAULT and cfg.get("credentials"):
        credentials = cfg.get("credentials")

    # Just like the log destination file, we only want to override
    # what came in from the CLI args if what came in was the default
    if ctx.get_parameter_source("kion_yaml") == Source.DEFAULT and cfg.get("kion_yaml"):
        kion_yaml = cfg.get("kion_yaml")

    if not all([profile, credentials, favourite]):
        raise ValueError(
            "Missing one configuration. Ensure configurtion file exists or all arguments are passed"
        )

    logging.debug(f"Profile: {profile}")
    logging.debug(f"Credentials File: {credentials}")
    logging.debug(f"Kion Favorite: {favourite}")
    logging.debug(f"Kion YAML: {kion_yaml}")

    if not creds_need_update(credentials, profile):
        logging.info("Credentials have not yet expired. Not updating.")
        return 0

    replace_kion_yaml(kion_yaml)
    aws_creds = get_new_aws_credentials(favourite)
    update_aws_credentials(credentials, profile, aws_creds)
