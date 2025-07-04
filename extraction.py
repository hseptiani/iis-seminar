import os
import re
import gzip
import time
import pandas as pd

# Define timestamp pattern globally
timestamp_pattern = re.compile(r'^\[(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) (\w) ([^\s\]]+) (\w+) ([^\]]+\]?)\]\s*(.*)$')
unknown_content = []

def parse_handle_request(content):
    '''
    Sample content:
    START HANDLE REQUEST: CHECK_SEQ params: [MF1, 1847608]
    START HANDLE REQUEST: CHECK_SEQ params: [MF2, 1847529, true]
    END HANDLE REQUEST: CHECK_SEQ params: [MF1, 1847608] result: 0 response time: 0ms
    END HANDLE REQUEST: CHECK_SEQ params: [MF2, 1847529, true] result: 1 response time: 0ms
    '''
    m = re.match(r'(START HANDLE REQUEST): (\w+) params: \[(.*?)\]', content)
    result = {}
    if m is None:
        m = re.match(r'(END HANDLE REQUEST): (\w+) params: \[(.*?)\] result: (-?\d+) response time: (\w+)', content)

    if m:
        result['stage'] = m[1]
        result['request'] = m[2]
        params = m[3].split(', ')
        result['area'] = params[0]
        result['mfs_id'] = params[1]
        result['force_check'] = None
        if len(params) > 2:
            result['force_check'] = params[2]

        if result['stage'] == "END HANDLE REQUEST":
            result['result'] = m[4]
            result['response_time'] = m[5]
    else:
        result['stage'] = 'unknown'
        result['data'] = content

    return result

def parse_execute_rbg(content):
    '''
    Sample content:
    try execute Task: TASK_ID: 199, TASK_TYPE: SingleTask CATEGORY: ON_TIME LOCKED: false POINTS: 1363 TELEGRAM_TYPE: FS LAM: 1 INFO: SingleTask - LAM(s)={1} LE: 1847529
    TASK_ID: 242, TASK_TYPE: LamTask CATEGORY: ON_TIME LOCKED: false POINTS: 807 TELEGRAM_TYPE: FS LAM: 1 INFO: LamTask - LAM(s)={1} SUBTASKS=[, SingleTask - LAM(s)={1} LE: 1847667, SingleTask - LAM(s)={1} LE: 1847668]
    TASK_ID: 240, TASK_TYPE: LamTask CATEGORY: ON_TIME LOCKED: true POINTS: 907 TELEGRAM_TYPE: FS LAM: 1 INFO: LamTask - LAM(s)={1} SUBTASKS=[, SingleTask - LAM(s)={1} LE: 1847717, SingleTask - LAM(s)={1} LE: 1847718] -- FAILURE: LamTask not allowed for UML transports. current LHM 1847717 [a_typ=UML] -- FAILURE: LamTask not allowed for UML transports. current LHM 1847717 [a_typ=UML]
    '''
    pattern = re.compile(r'(.*?)TASK_ID: (\d+), TASK_TYPE: (\w+) CATEGORY: (\w+) LOCKED: (\w+) POINTS: (\d+) TELEGRAM_TYPE: (\w+) LAM: (\d+) INFO: (.+?) SUBTASKS=\[, (.*?)\](.+)?')
    match = pattern.match(content)
    result = {}
    stage = task_id = task_type = category = locked = points = telegram_type = lam = info = le = fail_status = None
    les = []

    if match:
        stage, task_id, task_type, category, locked, points, telegram_type, lam, info, les, fail_status = match.groups()
        les = les.split(', ')
    else:
        pattern = re.compile(r'(.*?)TASK_ID: (\d+), TASK_TYPE: (\w+) CATEGORY: (\w+) LOCKED: (\w+) POINTS: (\d+) TELEGRAM_TYPE: (\w+) LAM: (\d+) INFO: (.+?) LE: (\d+)(.+)?')
        match = pattern.match(content)

        if match:
            stage, task_id, task_type, category, locked, points, telegram_type, lam, info, le, fail_status = match.groups()

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
        result['fail_status'] = fail_status
    else:
        # to capture "RBG 1 EVALUATED:" that always one before the whole executeRbg if stage is not "try execute task"
        pattern = re.compile(r'(RBG (\d+) EVALUATED): ')
        match = pattern.match(content)
        if match:
            result['stage'] = 'rbg'
            result['data'] = match.group(1)
        else:
            result['stage'] = 'unknown'
            result['data'] = content

    return result


def parse_vb(content):
    '''
    Sample content:
    id=1847583: VB not OK; result=false; info: #reserved=4, #VBOK=4
    id=1847754: VB not OK; result=false; info: isMoving=true, status=2, requiredStatusBit=4
    '''
    pattern = re.compile(r'id=(\d+): VB ([^;]+); result=(\w+); info:\s*(.*)')

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
            result['moving'] = None
            result['info_status'] = None
            result['requiredStatusBit'] = None
        else:
            m = re.match(r'isMoving=(\w+), status=(\d+), requiredStatusBit=(\d+)', vb_info)
            if m:
                result['reserved'] = None
                result['vbok'] = None
                result['moving'] = m.group(1)
                result['info_status'] = m.group(2)
                result['requiredStatusBit'] = m.group(3)
            else:
                result['stage'] = 'unknown'
                result['data'] = content

    return result


def parse_path_movement(content):
    '''
    Sample content:
    path search finished -- mfsId: 1847734; [true, [[[ 104008 -> 104100 ], [ 104100 -> 1410 ], [ 1410 -> 1418 ], [ 1418 -> 1715 ], [ 1715 -> 1716 ]]], 0]
    path search finished -- mfsId: 1847599; [false, [], -2]
    path search failed -- mfsTrans: [ mfs=1, mfs-id=1847599, 1631 -> 1716, checkLocal=63, checkRemote=8, distType=0, saveWay=true, minDist=0 ] failcode: -2
    '''
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
        else:
            result['search_status'] = 'unknown'
            result['data'] = content

    return result

def parse_alert(content):
    """
    Parses three kinds of alert-related lines:
      1) 'Alert empfangen: Name=..., Text=...'
      2) 'Start Alert-Verarbeitung: Alert=...,Lfdnr=...,Text=...'
      3) 'Alert <NAME> wurde verarbeitet. Text: '...' time: <n>[ms]'
    Returns a dict with at least 'stage', plus specific fields depending on which pattern matched.
    """
    result = {
        'stage': '',
        'alert_name': None,
        'lfdnr': None,
        'text': None,
        'time_ms': None
    }

    # 1) Alert empfangen
    m1 = re.match(r'\s*Alert empfangen:\s*Name=([^ ]+)\s*Text=(.*)', content)
    if m1:
        result['stage'] = 'Alert empfangen'
        result['alert_name'] = m1.group(1)
        result['text'] = m1.group(2).strip()
        return result

    # 2) Start Alert-Verarbeitung
    m2 = re.match(
        r'Start Alert-Verarbeitung: Alert=([^,]+),Lfdnr=(\d+),Text=(.*)',
        content
    )
    if m2:
        result['stage'] = 'Start Alert-Verarbeitung'
        result['alert_name'] = m2.group(1)
        result['lfdnr'] = m2.group(2)
        result['text'] = m2.group(3).strip()
        return result

    # 3) Alert <NAME> wurde verarbeitet
    m3 = re.match(
        r"Alert ([^ ]+) wurde verarbeitet\. Text: '(.*)' time: (\d+)\[ms\]",
        content
    )
    if m3:
        name = m3.group(1)
        result['stage'] = f'Alert {name} wurde verarbeitet'
        result['alert_name'] = name
        result['text'] = m3.group(2).strip()
        result['time_ms'] = m3.group(3)
        return result

    # fallback
    result['stage'] = 'unknown'
    result['data'] = content
    return result


def parse_telegram(content):
    """
    Parses two kinds of telegram-related lines:
      1) 'TelegramDispatch processed - success: <bool>, alert: <NAME>, text: <...>, telStructure: <...>'
      2) 'Alert <NAME> wurde gesendet. Text: '...''
    Returns a dict with at least 'stage', plus specific fields for whichever pattern matched.
    """
    result = {
        'stage': '',
        'success': None,
        'alert_name': None,
        'text': None,
        'tel_structure': None
    }

    # 1) TelegramDispatch processed
    m1 = re.match(
        r'TelegramDispatch processed - success: (\w+), alert: ([^,]+), '
        r'text: (.*), telStructure: (.+)',
        content
    )
    if m1:
        result['stage'] = 'TelegramDispatch processed'
        result['success'] = m1.group(1)
        result['alert_name'] = m1.group(2)
        result['text'] = m1.group(3).strip()
        result['tel_structure'] = m1.group(4)
        return result

    # 2) Alert <NAME> wurde gesendet
    m2 = re.match(r"Alert ([^ ]+) wurde gesendet\. Text: '(.+)'", content)
    if m2:
        name = m2.group(1)
        result['stage'] = f'Alert {name} wurde gesendet'
        result['alert_name'] = name
        result['text'] = m2.group(2)
        return result

    # fallback
    # result['stage'] = 'unknown'
    # result['data'] = content
    result = {'stage': 'unknown', 'data': content}
    return result


def check_sequence(content):
    pattern = re.compile(r'sequence check (\w+). id=(\d+) is (\w+). returned=(-?\d+)')
    match = pattern.match(content)
    result = {}

    if match:
        sequence_status, id, id_status, returned = match.groups()
        result['sequence_status'] = sequence_status
        result['id'] = id
        result['id_status'] = id_status
        result['returned'] = returned
    else:
        result['stage'] = 'unknown'
        result['data'] = content

    return result


def check_position(content):
    pattern = re.compile(r'CHECK_POSITION: LE id=(\d+) on position=(\d+), (seq=[^\s]+)')
    match = pattern.match(content)
    result = {}
    id = position = status = ''
    foundMatch = False

    if match:
        id, position, status = match.groups()
        foundMatch = True
    else:
        pattern = re.compile(r'LE id=(\d+): position=(\d+) is (.*)')
        match = pattern.match(content)

        if match:
            id, position, status = match.groups()
            foundMatch = True

    if foundMatch:
        result['id'] = id
        result['position'] = position
        result['status'] = status
    else:
        result['stage'] = 'unknown'
        result['data'] = content

    return result


def parse_path_detail(timestamp, mfs_id, paths):
    result = []
    order = 1
    for path in paths:
        new_path = {
            'timestamp': timestamp,
            'mfs_id': mfs_id,
            'order': order,
            'from': path['from'],
            'to': path['to']
        }
        result.append(new_path)
        order += 1

    return result

def getset_nio(content):
    'id=1857866: send to NIO=1746 (AUSSCHLEUSEN)'
    pattern = re.compile(r'id=(\d+): send to NIO=(\d+) (.*)')
    match = pattern.match(content)
    result = {}

    if match:
        id, send_to, status = match.groups()
        result['id'] = id
        result['send_to'] = send_to
        result['status'] = status
    else:
        result['stage'] = 'unknown'
        result['data'] = content

    return result


def collect_and_sort_log_lines(folder, max_files=None):
    timestamped_lines = []

    files = []
    for root, _, fs in os.walk(folder):
        for file in fs:
            # if file.endswith('.log') or file.endswith('.log.gz'):
            if file.endswith('.log.gz'):
                files.append(os.path.join(root, file))

    # Optional: Debug on a subset of files
    if max_files:
        files = sorted(files)[:max_files]

    for file_path in files:
        open_func = gzip.open if file_path.endswith('.gz') else open
        with open_func(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
            for line in f:
                m = timestamp_pattern.match(line)
                if m:
                    timestamp = m.group(1)
                    timestamped_lines.append((timestamp, line))

    # Sort all collected lines by timestamp
    timestamped_lines.sort(key=lambda x: x[0])
    return [line for _, line in timestamped_lines]


def add_to_unknown(function_name, parsed):
    parsed['stage'] = function_name
    unknown_content.append(parsed)


def write_request(data, function_name):
    filename = 'result/' + function_name + '.pkl.gz'
    df = pd.DataFrame(data)  # Convert list of dicts to DataFrame
    df.to_pickle(filename, compression='gzip')


if __name__ == '__main__':
    start_time = time.time() # Start timing

    start_handle_req = []
    end_handle_req = []
    execute_rbg = []
    is_vb_ok = []
    path_movement_finished = []
    path_detail = []
    path_movement_failed = []
    sequence = []
    position = []
    alerts_received = []
    alerts_processing = []
    alerts_handled = []
    alerts_unknown = []
    telegrams_processed = []
    telegrams_sent = []
    telegrams_unknown = []
    nio = []

    # Use max_files to debug, use None for full set
    # sorted_lines = collect_and_sort_log_lines("rawdata", max_files=50)
    sorted_lines = collect_and_sort_log_lines("rawdata")

    for line in sorted_lines:
        ts_match = timestamp_pattern.match(line)
        if ts_match:
            timestamp, info_code, thread, operation_num, function, content = ts_match.groups()
            function_name = function.split(".")[len(function.split(".")) - 1]

            # Start every dict with timestamp, info_code, thread and worker id
            parsed = {'timestamp': timestamp, 'info_code': info_code, 'thread': thread, 'operation_num': operation_num}

            # For every function, update the parsed dict with the return
            # and append the respective list
            # If not matched with regex in the function, should append to unknown by returning 'stage' and 'data'
            try:
                if function_name == 'executeRbg':
                    parsed.update(parse_execute_rbg(content))
                    if parsed['stage'] == 'unknown':
                        add_to_unknown(function_name, parsed)
                    elif parsed['stage'] == 'rbg':
                        rbg_stage = content
                    else:
                        if parsed['stage'] == '':
                            parsed['stage'] = rbg_stage
                        execute_rbg.append(parsed)

                elif function_name == 'handleRequest':
                    parsed.update(parse_handle_request(content))
                    if parsed['stage'] == 'START HANDLE REQUEST':
                        start_handle_req.append(parsed)
                    elif parsed['stage'] == 'END HANDLE REQUEST':
                        end_handle_req.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'isVBOK':
                    parsed.update(parse_vb(content))
                    if parsed['id']:
                        is_vb_ok.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'getPathForMovement':
                    parsed.update(parse_path_movement(content))
                    if parsed['search_status'] == 'finished':
                        path_detail.extend(parse_path_detail(parsed['timestamp'], parsed['mfs_id'], parsed['paths']))
                        path_movement_finished.append(parsed)
                    elif parsed['search_status'] == 'failed':
                        path_movement_failed.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'checkSequence':
                    parsed.update(check_sequence(content))
                    if parsed['sequence_status']:
                        sequence.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'isPositionOK':
                    parsed.update(check_position(content))
                    if parsed['id']:
                        position.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'mainLoop':
                    parsed.update(parse_alert(content))
                    if parsed['stage'] == 'Alert empfangen':
                        alerts_received.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'processAlert':
                    parsed.update(parse_alert(content))
                    if parsed['stage'] == 'Start Alert-Verarbeitung':
                        alerts_processing.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'alertHandler()':
                    parsed.update(parse_alert(content))
                    # matches "Alert <NAME> wurde verarbeitet"
                    if parsed['stage'].startswith('Alert') and 'wurde verarbeitet' in parsed['stage']:
                        alerts_handled.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                # --- TELEGRAM HANDLING ---
                elif function_name == 'fmRbgTelDisp':
                    parsed.update(parse_telegram(content))
                    if parsed['stage'] == 'TelegramDispatch processed':
                        telegrams_processed.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'send':
                    parsed.update(parse_telegram(content))
                    # matches "Alert <NAME> wurde gesendet"
                    if parsed['stage'].startswith('Alert') and 'wurde gesendet' in parsed['stage']:
                        telegrams_sent.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                elif function_name == 'getAndSetNioDestination':
                    parsed.update(getset_nio(content))
                    if parsed['id']:
                        nio.append(parsed)
                    else:
                        add_to_unknown(function_name, parsed)

                else:
                    # anything else
                    parsed['stage'] = function_name
                    parsed['data'] = content
                    add_to_unknown(function_name, parsed)


            except Exception as e:
                print(f"Error parsing function '{function_name}' at {timestamp}: {e}")
                exit(1)

    # Write the list into pkl file
    write_request(execute_rbg, 'Execute RBG')
    write_request(start_handle_req, 'Start Handle Request')
    write_request(end_handle_req, 'End Handle Request')
    write_request(is_vb_ok, 'Is VB OK')
    write_request(path_movement_finished, 'Path Movement Finished')
    write_request(path_detail, 'Path Movement Finished - Detail')
    write_request(path_movement_failed, 'Path Movement Failed')
    write_request(unknown_content, 'Unknown Content')
    write_request(alerts_received, 'Alerts Received')
    write_request(alerts_processing, 'Alerts Processing')
    write_request(alerts_handled, 'Alerts Handled')
    write_request(telegrams_processed, 'Telegrams Processed')
    write_request(telegrams_sent, 'Telegrams Sent')
    write_request(sequence, 'Check Sequence')
    write_request(position, 'Check Position')
    write_request(nio, 'Get Set NIO')

    end_time = time.time()  # End timing here
    print("Execution time:", end_time - start_time, "seconds")