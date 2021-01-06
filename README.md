# KBase JIRA report tool

This repo contains code for producing data for a sprint report from a JIRA instance.

It's also a bit Q&D and probably fragile to API changes.

## Instructions

1. Ensure python3 is installed:
```
$ which python3
/usr/bin/python3
```
2. Install `requests` and `python-dateutil`:
```
$ pip install requests python-dateutil
```
3. Clone the repo:
```
git clone https://github.com/MrCreosote/kbase_truss_data_upload_jira_report
```
4. [Create a JIRA API token](https://confluence.atlassian.com/cloud/api-tokens-938839638.html).
5. Run the script:
```
$ kbase_truss_data_upload_jira_report/get_jira_records.py 
No configuration file found
Enter your JIRA user name (typically an email address): g...@lbl.gov
Enter your JIRA API token. You can get one from https://confluence.atlassian.com/cloud/api-tokens-938839638.html: 
Please choose a JIRA board:
1	APS
*snip*
Enter JIRA board number: 7
Wrote configuration to /home/[user]/.truss_kbase_jira_summary.cfg. To make changes to the configuration you can edit that file manually or delete it to run this initialization routine again.
Please choose a sprint:
1	KBASEDAT Sprint 1
*snip*
Enter sprint number: 4
Found 39 tickets in sprint, fetching ticket history
Getting history for ticket DATAUP-15
*snip*
Ticket ID	Est. SP	 Act. SP	In Prog	Done
DATAUP-15	None	None	2020-08-10 16:16:55	2020-09-16 11:54:01
DATAUP-21	None	None	2020-09-02 11:01:35	2020-09-21 10:25:00
DATAUP-87	5.0	None	2020-09-08 13:04:20	
*snip*
```

After the first run of the script, only the sprint need be selected to get the report.

The report is tab delimited.

# Resources

* [JIRA Cloud API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
* [Jira Agile API](https://docs.atlassian.com/jira-software/REST/7.0.4/)

# Potential improvements:

* [Use OAuth2 rather than an API token](https://developer.atlassian.com/cloud/jira/platform/security-for-other-integrations/)
* Add tests. Since this is just a JIRA summarization tool for management reporting, if it fails
  it's not critical, so time hasn't been spent here yet.
* Add code comments for functions. See above.
* Better error presentation. Currently just dumps out the entire response body from JIRA.
  See above.
* Test timezone conversion more rigorously by changing the computer's timezome.
* Option to save to an output file in different formats (tab delimited, CSV)

# TODO
* Update code to
    * Pull data from all sprints
    * Print the numbers of the sprints where each ticket appears and is completed
* fix step 5 docs above when code update is done

# Previous implementation
https://github.com/MrCreosote/kbase_truss_data_upload_jira_report
