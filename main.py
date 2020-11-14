from prometheus_client import start_http_server, Gauge, Enum
import time
from requests import get
from validator_collection import checkers
from string import ascii_uppercase
from os import getenv

telegram_bot_api_url_stats = getenv("TELEGRAM_BOT_API_URL_STATS",
                                    "http://localhost:8082")
prometheus_port_exposition = int(getenv("PROMETHEUS_PORT_EXPOSITION",
                                        8000))
prometheus_time_refresh = int(getenv("PROMETHEUS_TIME_REFRESH",
                                     5))
# Create a metric to track time spent and requests made.
prometheus_data = {
    "uptime": Gauge('server_uptime', 'server uptime',
                    labelnames=('bot',)),
    "bot_count": Gauge('bot', 'bot count'),
    "active_bot_count": Gauge('active_bot', 'active bot count'),
    "total_cpu": Gauge('total_cpu', 'total cpu in percentage',
                       labelnames=('duration',)),
    "user_cpu": Gauge("user_cpu", 'user cpu in percentage',
                      labelnames=("duration",)),
    "system_cpu": Gauge('system_cpu', 'system cpu in percentage',
                        labelnames=('duration',)),
    "buffer_memory": Gauge('buffer_memory', 'buffer memory in byte'),
    "active_webhook_connections": Gauge("active_webhook_connections",
                                        "active webhook connections"),
    "active_requests": Gauge("active_requests", "active requests"),
    "active_network_queries": Gauge("active_network_queries",
                                    "active network queries"),
    "request_count": Gauge("request", "request/s count",
                           labelnames=('duration', 'bot')),
    "request_file_count": Gauge('request_file', 'request/s file',
                                labelnames=('duration',)),
    "response_count": Gauge('response', "response/s",
                            labelnames=("duration", 'type')),
    'update_count': Gauge('update', "update/s",
                          labelnames=("duration", 'bot')),
    "has_custom_certificate": Enum("has_custom_certificate",
                                   "has custom certificate",
                                   states=['true', 'false'],
                                   labelnames=('bot',)),
    "webhook_max_connections": Gauge("webhook_max_connections",
                                     "webhook max connections",
                                     labelnames=('bot',)),
}

BLACKLIST = ['token', 'request_bytes', 'request_files_bytes',
             'request_max_bytes', 'webhook', 'id', 'rss', 'vm', 'rss_peak',
             'vm_peak', 'response_bytes', 'head_update_id',
             'tail_update_id', 'pending_update_count', 'buffer_memory']
REPLACE = {
    "request_count/sec": "request_count",
    "update_count/sec": "update_count",
}


def decode(data: str) -> [int, float, bool, str]:
    if data.endswith('%'):
        data = data.replace('%', '')
    elif data.endswith("B"):
        i = len(data)
        for i, character in enumerate(data):
            if character in ascii_uppercase:
                break
        data, m = decode(data[:i]), data[i:].replace('B', '').lower()
        if m == 'm':
            m = 10 ** 6
        elif m == 'k':
            m = 10 ** 3
        return data * m
    if checkers.is_integer(data):
        return int(float(data))
    elif checkers.is_float(data):
        return float(data)
    elif data.lower() == 'false':
        return False
    elif data.lower() == 'true':
        return True
    else:
        return data


def get_data():
    data = get(telegram_bot_api_url_stats)
    all_data = {}
    section_data = {}
    for row in data.text.split('\n')[1:]:
        row = [decode(row_data) for row_data in row.split('\t')]
        if row[0] in BLACKLIST:
            continue
        if row[0] in REPLACE:
            row[0] = REPLACE[row[0]]
        if len(row) == 2:
            section_data.update({row[0]: row[1]})
        elif len(row) == 1:
            if len(all_data) == 0:
                all_data["server"] = section_data
            else:
                all_data[section_data.pop("username")] = section_data
            section_data = dict()
        else:
            section_data.update({row[0]: row[1:]})
    return all_data


def data_to_prometheus(datas: dict):
    for name , data in datas.items():
        labelvalues = {"bot": name}
        for row, values in data.items():
            if row == "response_count":
                label_response = {"type": "default"}
            elif row == "response_count_ok":
                label_response = {"type": "ok"}
                row = "response_count"
            elif row == "response_count_error":
                label_response = {"type": "error"}
                row = "response_count"
            else:
                label_response = {"type": None}
            if row in prometheus_data:
                collector = prometheus_data.copy()[row]
                if type(values) is not list:
                    values = [values]
                for value, duration in zip(values,
                                           ["inf", "5sec", "1min", "1hour"]):
                    label = dict()
                    if len(collector._labelnames) > 0:
                        #print(row, collector._labelvalues)
                        if "bot" in collector._labelnames:
                            label.update(labelvalues)
                        if "duration" in collector._labelnames:
                            label.update({"duration": duration})
                        if "type" in collector._labelnames:
                            label.update(label_response)
                        collector_test = collector.labels(**label)
                    else:
                        collector_test = collector
                    if type(collector_test) == Gauge:
                        collector_test.set(value)
                    elif type(collector_test) == Enum:
                        if value:
                            collector_test.state('true')
                        else:
                            collector_test.state('false')
            else:
                print(f"ERROR DATA:{row} Not found in prometheus")


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(prometheus_port_exposition)
    while True:
        data_to_prometheus(get_data())
        time.sleep(prometheus_time_refresh)
