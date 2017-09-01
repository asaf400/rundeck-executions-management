#!/usr/bin/python3

import json
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

import modules.base
from modules.logger import Logger
#from modules.rundeck import RundeckApi


def get_all_projects(only_names=True):
    '''Get every project info and returns only their names'''

    endpoint = URL + 'projects'
    project_info = []

    try:
        response = requests.get(endpoint, headers=HEADERS,
                                verify=False, timeout=CONFIGS['search_time'])
        projects_data = response.json()

        for project_data in projects_data:
            if only_names:
                project_info.append(project_data['name'])
            else:
                project_info.append(project_data)
    except requests.exceptions.RequestException as exception:
        if CONFIGS['verbose']:
            print(exception)
        return None

    return project_info


def get_jobs_by_project(project_name, only_ids=True):
    '''Get jobs by a given project '''

    endpoint = URL + 'project/' + project_name + '/jobs'
    job_info = []

    try:
        response = requests.get(endpoint, headers=HEADERS,
                                verify=False, timeout=CONFIGS['search_time'])
        jobs_data = response.json()

        for job_data in jobs_data:
            if only_ids:
                job_id = job_data.get('id')
                job_info.append(job_id)
            else:
                job_info.append(job_data)
    except requests.exceptions.RequestException as exception:
        if CONFIGS['verbose']:
            print(exception)
        return False

    return job_info


def get_executions(job_id, page, job_filter=True, only_ids=True):
    '''Get executions older than a given number of days by job or project '''

    execution_info = []

    if job_filter:
        endpoint = URL + 'job/' + job_id + '/executions'
        parameters = {
            'max': CONFIGS['delete_size'],
            'offset': page * CONFIGS['delete_size'],
        }
    else:
        endpoint = URL + 'project/' + job_id + '/executions'
        parameters = {
            'max': CONFIGS['delete_size'],
            'olderFilter': str(CONFIGS['keeping_days'])
        }

    try:
        response = requests.get(endpoint, params=parameters, headers=HEADERS,
                                verify=False, timeout=CONFIGS['search_time'])
        executions_data = response.json()

        for execution_data in executions_data['executions']:
            status = execution_data.get('status')

            if status != "running":
                if only_ids:
                    execution_id = execution_data.get('id')
                    execution_info.append(execution_id)
                else:
                    execution_info.append(execution_data)
    except requests.exceptions.RequestException as exception:
        if CONFIGS['verbose']:
            print(exception)
        return None

    return execution_info


def get_executions_total(identifier, job_filter=True):
    '''Get executions counter by project or job'''

    executions_count = 0

    if job_filter:
        endpoint = URL + 'job/' + identifier + '/executions'
    else:
        endpoint = URL + 'project/' + identifier + '/executions'

    parameters = {
        'olderFilter': str(CONFIGS['keeping_days']),
        'max': 1
    }

    try:
        response = requests.get(endpoint, params=parameters, headers=HEADERS,
                                verify=False, timeout=CONFIGS['search_time'])
        executions_data = response.json()
        executions_count = executions_data['paging']['total']
    except requests.exceptions.RequestException as exception:
        if CONFIGS['verbose']:
            print(exception)
        return None

    return executions_count


def delete_executions(executions_ids):
    '''Bulk deletions of Rundeck executions'''

    endpoint = URL + 'executions/delete'
    data = json.dumps(executions_ids)

    try:
        request = requests.post(
            endpoint, headers=HEADERS, data=data, verify=False, timeout=CONFIGS['delete_time'])
        response = request.json()

        if response['allsuccessful']:
            print("All requested executions were successfully deleted (total of {0})".
                  format(response['successCount']))
            return True
        else:
            print("Errors on deleting requested executions ({0}/{1} failed)".
                  format(response['failedCount'], response['requestCount']))
            return False
    except requests.exceptions.RequestException as exception:
        if CONFIGS['verbose']:
            print(exception)
        return False


# Calling main
if __name__ == "__main__":

    CONFIGS = modules.base.parse_args(
        'Listing running jobs and delete old logs from your Rundeck server.')
    LOGGING = Logger(level=2)

    if not modules.base.validate_keeping_time(CONFIGS['keeping_days']):
        LOGGING.write_to_log("Invalid parameter \'keeping_days\'. Exiting...")
        exit(1)

    if CONFIGS['over_ssl']:
        proto = 'https'
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    else:
        proto = 'http'

    URL = '{0}://{1}:{2}/api/{3}/'.format(
        proto, CONFIGS["hostname"], CONFIGS["port"], CONFIGS["api_version"])
    HEADERS = {
        'Content-Type': 'application/json',
        'X-Rundeck-Auth-Token': CONFIGS['token'],
        'Accept': 'application/json'
    }

    projects = get_all_projects()

    if projects is None:
        LOGGING.write_to_log("Error on reading Rundeck projects. Exiting...")
        exit(1)

    for project in projects:
        page_number = 0

        if CONFIGS['execs_by_project']:
            count_execs = get_executions_total(project, False)

            if count_execs is None:
                LOGGING.write_to_log("Error on reading counter of Rundeck executions. Exiting...")
                exit(1)

            total_pages = modules.base.get_num_pages(
                count_execs, CONFIGS["delete_size"])

            if count_execs > 0:
                LOGGING.write_to_log("[" + str(project) + "]: There are " + str(count_execs) +
                                     " old deletable executions", log_level=2)
                LOGGING.write_to_log("[" + str(project) + "]: Processing executions deleting in " +
                                     str(total_pages) + " cycles.", log_level=2)
            else:
                LOGGING.write_to_log("[" + str(project) + "]: There are no deletable executions",
                                     log_level=2)

            for actual_page in range(page_number, total_pages + 1):
                executions = get_executions(project, actual_page, False)

                if executions is None:
                    LOGGING.write_to_log("Error on reading Rundeck executions. Exiting...")
                    exit(1)
                else:
                    success = delete_executions(executions)
        else:
            jobs = get_jobs_by_project(project)
            for job in jobs:
                count_execs = get_executions_total(job)
                total_pages = modules.base.get_num_pages(
                    count_execs, CONFIGS["delete_size"])

                if count_execs > 0:
                    LOGGING.write_to_log("[" + str(project) + "]: There are " + str(count_execs) +
                                         " old deletable executions", log_level=2)
                    LOGGING.write_to_log("[" + str(project) + "]: Processing executions deleting in " +
                                         str(total_pages) + " cycles.", log_level=2)
                else:
                    LOGGING.write_to_log("[" + str(project) + "]: There are no deletable executions",
                                         log_level=2)

                for actual_page in range(page_number, total_pages + 1):
                    executions = get_executions(job, actual_page)

                    if executions:
                        success = delete_executions(executions)
                    elif not executions or not success:
                        break

    exit(0)
    