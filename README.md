# What this is
A script I developed circa 2021/2022 (can't exactly remember when) to sync members of an OpsGenie schedule to a Slack group.

The script was born out of our users' lack of visibility to the our team's OpsGenie schedule, which led them to mentioning everyone in the team whenever they need assistance (including those who aren't on the on-call roster).

# Required libraries
- requests

# Configuration
- Replace `OPSGENIE.GET_ON_CALLS.HEADERS.Authorization` with your Atlassian/OpsGenie API key
- Replace `OPSGENIE.GET_ON_CALLS.PATH_VARIABLES.:scheduleIdentifier:` with a list of your OpsGenie *schedule names* -- this will be indicated right above each schedule's timeline view
- Replace `SLACK.GET_USER_GROUP.FILTER.handle` with your Slack group's name, **without the @**
- Replace the following with your Slack API key:
  - `SLACK.GET_USER_GROUP.HEADERS.Authorization`
  - `SLACK.GET_USER_BY_EMAIL.HEADERS.Authorization`
  - `SLACK.SET_USER_GROUP_MEMBERS.HEADERS.Authorization`

# Running the script
- Use the `--verbose` flag if you need to output DEBUG-level log messages
- By default, the script runs in dry-run mode; ie. it will only fetch schedule, user and group details, but will not perform replacement of group member(s)
- Use the `--actual-run` flag to actually replace the group member(s) with those currently in the schedule

# To-dos
- Consolidate Slack API key into singular key:value under `SLACK`

# Licensing
See `LICENSE` for the original license, and `LICENSE.md` for the additional licensing clauses