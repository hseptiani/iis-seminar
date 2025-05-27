import re
import csv

def parse_handle_request(content):
    m = re.match(r'(START HANDLE REQUEST): (\w+) params: \[(.*?)\]', content)
    result = {}
    if m:
        result['stage'] = m[1]
        result['request'] = m[2]
        params = m[3].split(', ')
        result['area'] = params[0]
        result['le'] = params[1]
        result['force_check'] = 'null'
        if len(params) > 2:
            result['force_check'] = params[2]
    else:
        m = re.match(r'(END HANDLE REQUEST): (\w+) params: \[(.*?)\] result: (-?\d+) response time: (\w+)', content)
        if m:
            result['stage'] = m[1]
            result['request'] = m[2]
            params = m[3].split(', ')
            result['area'] = params[0]
            result['le'] = params[1]
            result['force_check'] = 'null'
            if len(params) > 2:
                result['force_check'] = params[2]
            result['result'] = m[4]
            result['response_time'] = m[5]
        else:
            result['stage'] = 'unknown'
            result['data'] = content

    return result

def parse_execute_rbg(content):
    pattern = re.compile(r'(.*?)TASK_ID: (\d+), TASK_TYPE: (\w+) CATEGORY: (\w+) LOCKED: (\w+) POINTS: (\d+) TELEGRAM_TYPE: (\w+) LAM: (\d+) INFO: (.+?) SUBTASKS=\[, (.*?)\]')
    match = pattern.match(content)
    result = {}
    stage = task_id = task_type = category = locked = points = telegram_type = lam = info = le = ''
    les = []

    if match:
        stage, task_id, task_type, category, locked, points, telegram_type, lam, info, les = match.groups()
        les = les.split(', ')
    else:
        pattern = re.compile(r'(.*?)TASK_ID: (\d+), TASK_TYPE: (\w+) CATEGORY: (\w+) LOCKED: (\w+) POINTS: (\d+) TELEGRAM_TYPE: (\w+) LAM: (\d+) INFO: (.+?) LE: (\d+)')
        match = pattern.match(content)

        if match:
            stage, task_id, task_type, category, locked, points, telegram_type, lam, info, le = match.groups()

    if match:
        result['stage'] = stage
        result['task_id'] = task_id
        result['task_type'] = task_type
        result['category'] = category
        result['locked'] = locked
        result['points'] = points
        result['telegram_type'] = telegram_type
        result['lam'] = lam
        result['info'] = info
        if task_type == 'SingleTask':
            result['le'] = le
        else:
            result['le'] = ''
            for item in les:
                m = re.match(r'.*? LE: (\d+)', item)
                if m:
                    if result['le'] == '':
                        result['le'] = m[1]
                    else:
                        result['le'] += ', ' + m[1]

    return result


def parse_vb(content):
    pattern = re.compile(r'id=(\d+): VB ([^;]+); result=(\w+); info: (.+)')
    match = pattern.match(content)
    result = {}

    if match:
        vb_id, vb_status, vb_result, vb_info = match.groups()
        result['id'] = vb_id
        result['vb_status'] = vb_status
        result['result'] = vb_result
        m = re.match(r'#reserved=(\d+), #VBOK=(\d+)', vb_info)
        if m:
            result['reserved'] = m.group(1)
            result['vbok'] = m.group(2)
            result['moving'] = ''
            result['info_status'] = ''
            result['requiredStatusBit'] = ''
        else:
            m = re.match(r'isMoving=(\w+), status=(\d+), requiredStatusBit=(\d+)', vb_info)
            if m:
                result['reserved'] = ''
                result['vbok'] = ''
                result['moving'] = m.group(1)
                result['info_status'] = m.group(2)
                result['requiredStatusBit'] = m.group(3)
            else:
                result['stage'] = 'unknown'
                result['data'] = content

    return result


def parse_path_movement(content):
    main_pattern = re.compile(r'path search (finished) -- mfsId: (\d+); \[(\w+), (\[\[\[.*?\]\]\]|\[\]), (-?\d+)\]')
    match = main_pattern.match(content)
    result = {}

    if match:
        search_status, mfs_id, status, path_block, code = match.groups()

        path_pattern = re.compile(r'\[\s*(\d+)\s*->\s*(\d+)\s*\]')
        raw_paths = path_pattern.findall(path_block)

        result = {
            'search_status': search_status,
            'mfs_id': mfs_id,
            'status': status,
            'code': code,
            'paths': [{'from': start, 'to': end} for start, end in raw_paths]
        }
    else:
        main_pattern = re.compile(r'path search (failed) -- mfsTrans: \[ mfs=(\d+), mfs-id=(\d+), (\d+) -> (\d+), checkLocal=(\d+), checkRemote=(\d+), distType=(\d+), saveWay=(\w+), minDist=(-?\d+) \] failcode: (-?\d+)')
        match = main_pattern.match(content)

        if match:
            search_status, mfs, mfs_id, path_from, path_to, check_local, check_remote, dist_type, save_way, min_dist, failcode = match.groups()

            result = {
                'search_status': search_status,
                'mfs': mfs,
                'mfs_id': mfs_id,
                'path_from': path_from,
                'path_to': path_to,
                'check_local': check_local,
                'check_remote': check_remote,
                'dist_type': dist_type,
                'save_way': save_way,
                'min_dist': min_dist,
                'failcode': failcode
            }

    return result


def write_request(data, function_name):
    filename = 'result/' + function_name + '.csv'
    with open(filename, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)


if __name__ == '__main__':
    original_raw_file = 'RawDataSigment1'
    file_path = 'rawdata/' + original_raw_file + '.log'

    # with gzip.open(file_path, 'rt', encoding='utf-8') as f:
    # lines = [line.strip() for line in f if line.strip()]
    with open(file_path) as f:
        lines = f.readlines()

    timestamp_pattern = re.compile(r'^\[(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (\w) (\w+) (\w+) ([^\]]+)\]\s*(.*)$')
    start_handle_req = []
    end_handle_req = []
    execute_rbg = []
    is_vb_ok = []
    path_movement_finished = []
    path_movement_failed = []
    unknown_content = []

    a = 0
    for line in lines:
        ts_match = timestamp_pattern.match(line)
        if ts_match:
            timestamp, log_level, module, worker_id, function, content = ts_match.groups()
            function_name = function.split(".")[len(function.split("."))-1]
            parsed = {'timestamp': timestamp, 'module': module, 'worker_id': worker_id}

            try:
                if function_name == 'executeRbg':
                    parsed.update(parse_execute_rbg(content))
                    execute_rbg.append(parsed)
                elif function_name == 'handleRequest':
                    parsed.update(parse_handle_request(content))

                    if parsed['stage'] == 'START HANDLE REQUEST':
                        start_handle_req.append(parsed)
                    elif parsed['stage'] == 'END HANDLE REQUEST':
                        end_handle_req.append(parsed)
                    else:
                        unknown_content.append(parsed)
                elif function_name == 'isVBOK':
                    parsed.update(parse_vb(content))

                    if parsed['id']:
                        is_vb_ok.append(parsed)
                    else:
                        unknown_content.append(parsed)
                elif function_name == 'getPathForMovement':
                    parsed.update(parse_path_movement(content))
                    if parsed['search_status'] == 'finished':
                        path_movement_finished.append(parsed)
                    else:
                        path_movement_failed.append(parsed)
                else:
                    u = {'stage': function_name, 'data': content}
                    parsed.update(u)
                    unknown_content.append(parsed)

            except Exception as e:
                print(function_name, timestamp)
                exit(1)

    write_request(execute_rbg, 'Execute RBG')
    write_request(start_handle_req, 'Start Handle Request')
    write_request(end_handle_req, 'End Handle Request')
    write_request(is_vb_ok, 'IsVBOK')
    write_request(path_movement_finished, 'Path Movement Finished')
    write_request(path_movement_failed, 'Path Movement Failed')
    write_request(unknown_content, 'Unknown Content')