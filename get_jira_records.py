#!/usr/bin/env python3

# Passing the config around all over the place is pretty gross, esp considering that different
# functions expect different parts of the config to be present.
# If this ever becomes a tool that more than a few people use, that whole strategy should
# be rethought as it's not very maintainable.

import base64
import datetime
import dateutil.parser
import getpass
import os
import requests

from collections import defaultdict
from configparser import ConfigParser
from pathlib import Path

CONFIG_FILE = '.kbase_jira_summary.cfg'
SEC_CREDS = 'Credentials'
SEC_JIRA = 'JIRA settings'
CFG_USERNAME = 'username'
CFG_API_TOKEN = 'api_token'
CFG_BOARD = 'board_id'
CFG_IGNORE_SPRINTS = 'ignore_sprints'

JIRA_URL = 'https://kbase-jira.atlassian.net'
JIRA_API_TOKEN_URL = 'https://confluence.atlassian.com/cloud/api-tokens-938839638.html'
JIRA_MYSELF = '/rest/api/3/myself/'
JIRA_BOARDS = '/rest/agile/1.0/board/'
JIRA_SEARCH = '/rest/api/3/search/'
JIRA_ISSUE = '/rest/api/3/issue/'
JIRA_SPRINT_SUFFIX = '/sprint'
JIRA_CHANGELOG_SUFFIX = '/changelog'
QUERY_MAX_RESULTS = 'maxResults'
QUERY_START_AT = 'startAt'
QUERY_JQL = 'jql'
RESULT_IS_LAST = 'isLast'
RESULT_VALUES = 'values'
RESULT_NAME = 'name'
RESULT_ID = 'id'
RESULT_ISSUES = 'issues'
RESULT_TOTAL = 'total'
RESULT_KEY = 'key'
RESULT_ITEMS = 'items'
RESULT_FIELD_ID = 'fieldId'
RESULT_CREATED = 'created'
RESULT_TO = 'to'
RESULT_FIELDS = 'fields'
FLD_STORY_POINT_ACTUAL = 'customfield_11164'
FLD_STORY_POINT_EST = 'customfield_11127'
FLD_SUMMARY = 'summary'
FLD_ASSIGNEE = 'assignee'
FLD_DISPLAY_NAME = 'displayName'

CHANGELOG_STATUS = 'status'
CHANGELOG_INPROG_ID = '10685'
CHANGELOG_DONE_ID = '10686'

DS_KEY = 'key'
DS_STORY_POINT_ACTUAL = 'spa'
DS_STORY_POINT_EST = 'spe'
DS_TITLE = 'title'
DS_SPRINTS = 'sprints'
DS_SPRINT_NAME = 'spname'
DS_USER = 'user'
DS_TICKETS = 'tickets'
DS_IN_PROGRESS = 'inprog'
DS_DONE = 'done'


DT_MAX = datetime.datetime(datetime.MAXYEAR, 12, 12, tzinfo=datetime.timezone.utc)
DT_MIN = datetime.datetime(datetime.MINYEAR, 1, 1, tzinfo=datetime.timezone.utc)


MAX_RESULTS = 10000


def get_auth_headers(username, token):
    return {'Authorization': 'Basic ' + base64.b64encode(
        f'{username}:{token}'.encode('UTF-8')).decode('UTF-8')}


def get_auth_headers_from_config(cfg):
    username = cfg[SEC_CREDS][CFG_USERNAME]
    token = cfg[SEC_CREDS][CFG_API_TOKEN]
    return get_auth_headers(username, token)


def check_creds(username, token):
    resp = requests.get(JIRA_URL + JIRA_MYSELF, headers=get_auth_headers(username, token))
    if not resp.ok:
        raise ValueError('Authentication to JIRA failed:\n' + resp.text)


def load_config(cfgfile):
    cfg = ConfigParser()
    cfg.read(cfgfile)
    # TODO check config is valid - no missing keys, creds work, board ID is an int
    return cfg_to_dict(cfg)


def cfg_to_dict(cfg):
    ignore = cfg[SEC_JIRA].get(CFG_IGNORE_SPRINTS)
    ignore = [t.strip() for t in ignore.split(';') if t.strip()] if ignore else []
    ret = {CFG_USERNAME: cfg[SEC_CREDS][CFG_USERNAME],
           CFG_API_TOKEN: cfg[SEC_CREDS][CFG_API_TOKEN],
           CFG_BOARD: int(cfg[SEC_JIRA][CFG_BOARD]),
           CFG_IGNORE_SPRINTS: ignore}
    return ret


# *** side effect *** - adds username, token, & comments to config
def get_user_pass(cfg):
    username = input('Enter your JIRA user name (typically an email address): ').strip()
    token = getpass.getpass(
        f'Enter your JIRA API token. You can get one from {JIRA_API_TOKEN_URL}: ').strip()
    check_creds(username, token)
    
    cfg.add_section(SEC_CREDS)
    cfg.set(SEC_CREDS, '# The JIRA account username, often an email address.', None)
    cfg[SEC_CREDS][CFG_USERNAME] = username
    cfg.set(SEC_CREDS, '# An API token for the JIRA account, obtainable from ', None)
    cfg.set(SEC_CREDS, '# ' + JIRA_API_TOKEN_URL, None)
    cfg[SEC_CREDS][CFG_API_TOKEN] = token


def get_jira_selection(username, token, url, name):
    headers = get_auth_headers(username, token)

    not_complete = True
    items = {}
    start_at = 0
    while not_complete:
        resp = requests.get(
            url,
            params={QUERY_MAX_RESULTS: MAX_RESULTS, QUERY_START_AT: start_at},
            headers=headers)
        if not resp.ok:
            raise ValueError(f'Failed to get {name}s:\n{resp.text}')
        j = resp.json()
        not_complete = not j[RESULT_IS_LAST]
        start_at = start_at + len(j[RESULT_VALUES])
        
        for item in j[RESULT_VALUES]:
            items[item[RESULT_NAME]] = item[RESULT_ID]
    sorted_items = [(b, items[b]) for b in sorted(items)]
    
    print(f'Please choose a {name}:')
    for i, (item, _) in enumerate(sorted_items):
        print(f'{i + 1}\t{item}')
    # could do a loop here, but assume the ppl using this are relatively intelligent
    item_num = input(f'Enter {name} number: ').strip()
    try:
        item_num = int(item_num)
    except ValueError:
        raise ValueError(f'Please enter an integer between 1-{len(sorted_items)}')
    if item_num < 1 or item_num > len(sorted_items):
        raise ValueError(f'Please enter an integer between 1-{len(sorted_items)}')
    return sorted_items[item_num - 1][1]
    

# *** side effect *** adds board ID to config
def get_jira_board(cfg):
    board_id = get_jira_selection(
        cfg[SEC_CREDS][CFG_USERNAME],
        cfg[SEC_CREDS][CFG_API_TOKEN],
        f'{JIRA_URL}{JIRA_BOARDS}',
        'JIRA board'
    )
    cfg.add_section(SEC_JIRA)
    cfg.set(SEC_JIRA, '# The ID of the JIRA agile board.', None)
    cfg[SEC_JIRA][CFG_BOARD] = str(board_id)
    cfg.set(
        SEC_JIRA,
        '# Ignore selected sprints. Enter substrings of sprints to ignore, ' +
            'separated by semicolons',
        None)
    cfg.set(SEC_JIRA, CFG_IGNORE_SPRINTS, '')

def get_config(cfgfile):
    cfg = ConfigParser(allow_no_value=True)
    get_user_pass(cfg)
    get_jira_board(cfg)

    with open(cfgfile, 'w') as f:
        cfg.write(f)
    print(f'Wrote configuration to {cfgfile}. To make changes to the configuration you can ' +
        'edit that file manually or delete it to run this initialization routine again.')

    return cfg_to_dict(cfg)

def get_sprints(username, token, board_id, ignore_sprints):
    headers = get_auth_headers(username, token)

    not_complete = True
    items = {}
    start_at = 0
    while not_complete:
        resp = requests.get(
            f'{JIRA_URL}{JIRA_BOARDS}{board_id}{JIRA_SPRINT_SUFFIX}',
            params={QUERY_MAX_RESULTS: MAX_RESULTS, QUERY_START_AT: start_at},
            headers=headers)
        if not resp.ok:
            raise ValueError(f'Failed to get sprints:\n{resp.text}')
        j = resp.json()
        not_complete = not j[RESULT_IS_LAST]
        start_at = start_at + len(j[RESULT_VALUES])
        
        for item in j[RESULT_VALUES]:
            if not ignored(item[RESULT_NAME], ignore_sprints):
                items[item[RESULT_ID]] = {DS_SPRINT_NAME: item[RESULT_NAME]}
    sorted_items = [(b, items[b]) for b in sorted(items)]
    return sorted_items


def ignored(sprint_name, ignore_sprints):
    for ig in ignore_sprints:
        if ig in sprint_name:
            return True
    return False


def get_tickets(username, token, sprint_id):
    # close to get_jira_selection but not enough that I want to DRY it up right now
    # need to pass in query params & collector for results
    headers = get_auth_headers(username, token)

    not_complete = True
    keys = []
    start_at = 0
    while not_complete:
        resp = requests.get(
            f'{JIRA_URL}{JIRA_SEARCH}',
            params={QUERY_MAX_RESULTS: MAX_RESULTS,
                    QUERY_START_AT: start_at,
                    QUERY_JQL: f'sprint = {sprint_id}'
                    },
            headers=headers)
        if not resp.ok:
            raise ValueError(f'Failed to get JIRA tickets:\n{resp.text}')
        j = resp.json()
        start_at = start_at + len(j[RESULT_ISSUES])
        not_complete = j[RESULT_TOTAL] > start_at

        for item in j[RESULT_ISSUES]:
            assign = item[RESULT_FIELDS][FLD_ASSIGNEE]
            keys.append({DS_KEY: item[RESULT_KEY],
                         DS_TITLE: item[RESULT_FIELDS].get(FLD_SUMMARY),
                         DS_STORY_POINT_EST: item[RESULT_FIELDS].get(FLD_STORY_POINT_EST),
                         DS_STORY_POINT_ACTUAL: item[RESULT_FIELDS].get(FLD_STORY_POINT_ACTUAL),
                         DS_USER: assign[FLD_DISPLAY_NAME] if assign else 'Unassigned'
            })
    # assumes all keys in sprint have the same prefix
    # may need simple adjustment if not
    return sorted(keys, key=lambda k: int(k[DS_KEY].split('-')[1]))


def get_ticket_data(username, token, tickets):
    headers = get_auth_headers(username, token)
    tickets2 = {}
    for t in sorted(tickets, key=lambda k: int(k.split('-')[-1])):
        print(f'Getting history for ticket {t}')
        # close to get_jira_selection but not enough that I want to DRY it up right now
        # need to pass in collector for results
        not_complete = True
        in_prog = DT_MAX
        done = DT_MIN
        start_at = 0
        while not_complete:
            resp = requests.get(
                f'{JIRA_URL}{JIRA_ISSUE}{t}{JIRA_CHANGELOG_SUFFIX}',
                params={QUERY_MAX_RESULTS: MAX_RESULTS,
                        QUERY_START_AT: start_at,
                        },
                headers=headers)
            if not resp.ok:
                raise ValueError(f'Failed to get JIRA ticket:\n{resp.text}')
            j = resp.json()
            start_at = start_at + len(j[RESULT_VALUES])
            not_complete = not j[RESULT_IS_LAST]

            # changes are ordered by time
            for change in j[RESULT_VALUES]:
                created = dateutil.parser.isoparse(change[RESULT_CREATED])
                for item in change[RESULT_ITEMS]:
                    if item.get(RESULT_FIELD_ID) == CHANGELOG_STATUS:
                        # something strikes me as off about this logic...
                        if item[RESULT_TO] == CHANGELOG_INPROG_ID and created < in_prog:
                            in_prog = created
                        if item[RESULT_TO] == CHANGELOG_DONE_ID and created > done:
                            done = created
                        if item[RESULT_TO] != CHANGELOG_DONE_ID:
                            done = DT_MIN
        done = None if done == DT_MIN else done
        in_prog = None if in_prog == DT_MAX else in_prog
        t2 = {DS_IN_PROGRESS: in_prog, DS_DONE: done}
        t2.update(tickets[t])
        tickets2[t] = t2
    return tickets2


def print_ticket(ticket):
    # So the JIRA servers send the timestamps in CA time (-7 GMT), so it's not 100% clear
    # that the timezone conversion is correct since I'm in CA.
    # I'd prefer to leave the TZ info in, but Google Sheets can't handle it, which 
    # kind of blows my mind.
    ip = ticket[DS_IN_PROGRESS].astimezone(tz=None) if ticket[DS_IN_PROGRESS] else None
    done = ticket[DS_DONE].astimezone(tz=None) if ticket[DS_DONE] else None
    
    print(f'{ticket[DS_KEY]}\t', end='')
    print(f'{ticket[DS_STORY_POINT_EST]}\t{ticket[DS_STORY_POINT_ACTUAL]}\t', end='')
    if ip:
        print(f'{ip:%Y-%m-%d %H:%M:%S}\t', end='')
    else:
        print('\t', end='')
    if done:
        print(f'{done:%Y-%m-%d %H:%M:%S}\t', end='')
    else:
        print('\t', end='')
    print(f'{",".join([str(t) for t in ticket[DS_SPRINTS]])}', end='')
    print(f'\t{ticket[DS_USER]}\t{ticket[DS_TITLE]}')

def main():
    cfgfile = Path(os.path.expanduser('~')) / CONFIG_FILE
    if cfgfile.is_dir():
        raise ValueError(f'Configuration file {cfgfile} is a directory')
    if cfgfile.exists():
        print(f'Found configuration file {cfgfile}, loading')
        cfg = load_config(cfgfile)
    else:
        print(f'No configuration file found')
        cfg = get_config(cfgfile)

    username = cfg[CFG_USERNAME]
    token = cfg[CFG_API_TOKEN]
    sprints = get_sprints(username, token, cfg[CFG_BOARD], cfg[CFG_IGNORE_SPRINTS])
    tickets = {}
    for sprint_id, sprint_data in sprints:
        print(f'Getting tickets for sprint {sprint_data[DS_SPRINT_NAME]} (ID {sprint_id})')
        tick = get_tickets(username, token, sprint_id)
        sprint_data[DS_TICKETS] = [t[DS_KEY] for t in tick]
        for t in tick:
            if t[DS_KEY] in tickets and tickets[t[DS_KEY]] != t:
                raise ValueError(f'ticket data not equal to prior data for sprint {sprint_id}')
            tickets[t[DS_KEY]] = t
    print(f'Found {len(tickets)} tickets in sprints, fetching ticket history')
    tickets = get_ticket_data(username, token, tickets)
    for t in tickets:
        tickets[t][DS_SPRINTS] = []
    for i, sprint in enumerate(sprints):
        for t in sprint[1][DS_TICKETS]:
            tickets[t][DS_SPRINTS].append(i + 1)

    print()
    print('Sprint #\tSprint Name')
    for i, (_, sprint) in enumerate(sprints):
        print(f'{i + 1}\t{sprint[DS_SPRINT_NAME]}')
    print()
    print(f'Ticket count: {len(tickets)}')
    print('Ticket ID\tEst. SP\t Act. SP\tIn Prog\tDone\tSprints\tTitle')
    # sort by the last sprint containing the ticket, then by the ticket number
    for t in sorted(tickets, key=lambda k: (tickets[k][DS_SPRINTS][-1], int(k.split('-')[-1]))):
        print_ticket(tickets[t])


if __name__ == '__main__':
    main()
