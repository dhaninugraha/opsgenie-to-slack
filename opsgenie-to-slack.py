from logging.handlers import TimedRotatingFileHandler
import requests
import argparse
import logging
import json
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))

config = None
with open(os.path.join(project_root, 'config.json')) as config_file:
    config = json.load(config_file)

if config is None:
    print('Error loading config.json, exiting now')
    sys.exit(1)

""" command line arguments """
arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--actual-run',
                        action='store_true'
                        )
arg_parser.add_argument('--verbose',
                        help='Prints DEBUG messages',
                        action='store_true'
                        )
args = arg_parser.parse_args()
""" end of command line arguments """

""" logging configuration """
# set default values for logging, in case the one in config.json got wiped or was misconfigured
logging.getLogger("urllib3").setLevel(logging.WARNING)

LOGGER_NAME = config['LOGGER_NAME'] or 'who-is-on-call'
LOG_FORMAT = config['LOG_FORMAT']['PLAIN'] or '%(name)s - %(asctime)s - %(levelname)s - %(message)s'
LOG_FILE_NAME = config['LOG_FILE_NAME'] or 'who-is-on-call.log'
LOG_FILE_ROTATE_WHEN = config['LOG_FILE_ROTATE_WHEN'] or 'midnight'
LOG_BACKUP_COUNT = config['LOG_BACKUP_COUNT'] or 7
LOG_USE_UTC = config['LOG_USE_UTC'] or True

# set log level to DEBUG if the script is run with the --verbose flag
log_level = logging.INFO
if args.verbose:
    log_level = logging.DEBUG

# StreamHandler will output logs to stdout
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(logging.Formatter(LOG_FORMAT))
stdout_handler.setLevel(log_level)

# RotatingFileHandler will output logs to a defined logfile and handle rotation as well
rotating_file_handler = TimedRotatingFileHandler(
    os.path.join(project_root, LOG_FILE_NAME),
    when=LOG_FILE_ROTATE_WHEN,
    backupCount=LOG_BACKUP_COUNT,
    utc=LOG_USE_UTC
)
rotating_file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
rotating_file_handler.setLevel(log_level)

log_handlers = [stdout_handler, rotating_file_handler]  # if we were to define more handlers, put them in here as well
logging.basicConfig(level=log_level, handlers=log_handlers)
log = logging.getLogger(LOGGER_NAME)
""" end of logging configuration """


def call_api(method: str, url: str, headers: dict, query_params: dict) -> requests.Response:
    with requests.Session() as s:
        log.debug(f'Request: {method} {url}')

        resp = s.request(
            method=method,
            url=url,
            headers=headers,
            params=query_params
        )

        log.debug(f'Response code: {resp.status_code}')

        return resp


def opsgenie_get_current_on_calls(config: dict) -> list:
    current_on_calls: list = []

    for schedule_identifier in config['OPSGENIE']['GET_ON_CALLS']['PATH_VARIABLES'][':scheduleIdentifier:']:
        log.info(f'Getting on-calls for schedule: {schedule_identifier}')
        resp = call_api(
            config['OPSGENIE']['GET_ON_CALLS']['METHOD'],
            config['OPSGENIE']['GET_ON_CALLS']['URL'].replace(':scheduleIdentifier:', schedule_identifier),
            config['OPSGENIE']['GET_ON_CALLS']['HEADERS'],
            config['OPSGENIE']['GET_ON_CALLS']['QUERY_PARAMS']
        )

        if resp.status_code == requests.codes.ok:
            for on_call_recipient in resp.json()['data']['onCallRecipients']:
                current_on_calls.append(on_call_recipient)

    log.info(f'Current on calls: {current_on_calls}')

    return current_on_calls


def slack_get_user_group_id(config: dict) -> tuple[str, str]:
    log.info(f'Getting group ID for Slack user group @{config["SLACK"]["GET_USER_GROUP"]["FILTER"]["handle"]}')
    log.debug(f'User group filter condition: {config["SLACK"]["GET_USER_GROUP"]["FILTER"]}')

    user_group: dict = {}
    user_group_id: str = ''
    team_id: str = ''

    resp = call_api(
        config['SLACK']['GET_USER_GROUP']['METHOD'],
        config['SLACK']['GET_USER_GROUP']['URL'],
        config['SLACK']['GET_USER_GROUP']['HEADERS'],
        config['SLACK']['GET_USER_GROUP']['QUERY_PARAMS']
    )

    if resp.status_code == requests.codes.ok:
        if resp.json()['ok']:
            for usergroup in resp.json()['usergroups']:
                if ('handle', config['SLACK']['GET_USER_GROUP']['FILTER']['handle']) in usergroup.items():
                    log.debug(usergroup)

                    user_group = usergroup

                    break

    if 'id' in user_group:
        if user_group['id'] is not None and len(str(user_group['id'])) > 0:
            user_group_id = str(user_group['id'])
            team_id = str(user_group['team_id'])

    log.info(
        f'User group: @{config["SLACK"]["GET_USER_GROUP"]["FILTER"]["handle"]}, group ID: {user_group_id}, team ID: {team_id}')

    return user_group_id, team_id


def slack_get_user_ids_by_emails(config: dict, current_on_call_emails: list) -> list:
    log.info(f'Getting associated Slack user ID from the following emails: {current_on_call_emails}')

    if type(current_on_call_emails) != list:
        log.error('slack_get_user_ids_by_emails() is expecting a list')
        sys.exit(1)

    if len(current_on_call_emails) == 0:
        log.error('slack_get_user_ids_by_emails() is expecting a non-empty list')
        sys.exit(1)

    user_ids = []
    for email in current_on_call_emails:
        resp = call_api(
            config['SLACK']['GET_USER_BY_EMAIL']['METHOD'],
            config['SLACK']['GET_USER_BY_EMAIL']['URL'],
            config['SLACK']['GET_USER_BY_EMAIL']['HEADERS'],
            {'email': email}
        )

        if resp.status_code == requests.codes.ok:
            if resp.json()['ok']:
                log.info(f'Email: {email}, Slack user ID: {resp.json()["user"]["id"]}')
                log.debug(resp.json()['user'])

                user_ids.append(resp.json()['user']['id'])

    log.debug(user_ids)

    return (user_ids)


def slack_set_user_group_members(config: dict, user_group_id: str, team_id: str, user_ids: str):
    log.info(f'Updating Slack group {user_group_id} in team {team_id} with the following users: {user_ids}')

    resp = call_api(
        config['SLACK']['SET_USER_GROUP_MEMBERS']['METHOD'],
        config['SLACK']['SET_USER_GROUP_MEMBERS']['URL'],
        config['SLACK']['SET_USER_GROUP_MEMBERS']['HEADERS'],
        {'usergroup': user_group_id, 'users': user_ids, 'team_id': team_id}
    )

    log.debug(resp.status_code)
    log.debug(resp.json())

    if resp.status_code == requests.codes.ok:
        if resp.json()['ok']:
            log.info('Successfully updated the user group')


if __name__ == '__main__':
    if not args.actual_run:
        log.info('Running in dry-run mode; nothing will be updated')
    else:
        log.info('Running in actual-run mode; Slack user group will be updated')

    current_on_calls = opsgenie_get_current_on_calls(config)
    current_on_call_ids = ','.join(slack_get_user_ids_by_emails(config, current_on_calls))
    user_group_id, team_id = slack_get_user_group_id(config)

    if args.actual_run:
        slack_set_user_group_members(config, user_group_id, team_id, current_on_call_ids)
