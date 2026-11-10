"""Read-only RM2000/2003 export using the official EasyRPG LCF2XML converter."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def number(node, key, default=0):
    return int(node.findtext(key) or default)


def write_csv(path, rows, columns):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def export(source: Path, output: Path, xml_dir: Path, converter: Path | None):
    source, output, xml_dir = source.resolve(), output.resolve(), xml_dir.resolve()
    if converter is not None and not converter.is_file():
        raise ValueError('LCF2XML converter not found: ' + str(converter))
    if output.is_relative_to(source) or xml_dir.is_relative_to(source):
        raise ValueError('Outputs must be outside the original sample directory')
    inputs = sorted([*source.glob('*.ldb'), *source.glob('*.lmt'), *source.glob('*.lmu')])
    if not inputs:
        raise ValueError('No LCF input files')
    before = {p.name: sha256(p) for p in inputs}
    xml_dir.mkdir(parents=True, exist_ok=True)
    if converter:
        # ASCII basenames avoid legacy Windows argv/path encoding problems.
        copied = xml_dir.parent / 'input'
        copied.mkdir(exist_ok=True)
        for path in inputs:
            shutil.copyfile(path, copied / path.name)
        for offset in range(0, len(inputs), 25):
            argv = [str(converter.resolve()), '--2k3', '--encoding', 'CP936']
            argv += [str((copied / p.name).resolve()) for p in inputs[offset:offset + 25]]
            proc = subprocess.run(argv, cwd=xml_dir, capture_output=True, timeout=120)
            if proc.returncode:
                raise RuntimeError(proc.stderr.decode('utf-8', errors='replace'))
    expected = {p.with_suffix({'.ldb': '.edb', '.lmt': '.emt', '.lmu': '.emu'}[p.suffix]).name for p in inputs}
    if not all((xml_dir / name).exists() for name in expected):
        raise ValueError('XML output set is incomplete')
    output.mkdir(parents=True, exist_ok=True)
    codes = json.loads((Path(__file__).with_name('lcf_event_codes.json')).read_text(encoding='utf-8'))
    database = ET.parse(xml_dir / 'RPG_RT.edb').getroot().find('Database')
    tree = ET.parse(xml_dir / 'RPG_RT.emt').getroot().find('TreeMap')
    map_infos = {int(x.get('id')): x for x in tree.findall('maps/MapInfo')}
    start = {x.tag: int(x.text or '0') for x in tree.find('start/Start')}
    entities = {}
    for kind in ['actors', 'skills', 'items', 'enemies', 'troops', 'switches', 'variables', 'commonevents']:
        entities[kind] = [dict(id=int(x.get('id')), name=x.findtext('name') or '') for x in database.find(kind)]
    for kind in ['actors', 'skills', 'items', 'enemies', 'switches', 'variables', 'commonevents']:
        rows = []
        for entity in database.find(kind):
            row = {'id': int(entity.get('id')), 'name': entity.findtext('name') or ''}
            if kind == 'actors':
                row.update(initial_level=number(entity, 'initial_level'), final_level=number(entity, 'final_level'))
                pars = entity.find('parameters/Parameters')
                for key in ['maxhp', 'maxsp', 'attack', 'defense', 'spirit', 'agility']:
                    values = (pars.findtext(key) or '').split() if pars is not None else []
                    row['level1_' + key] = int(values[0]) if values else None
            elif kind == 'items':
                for key in ['type', 'price', 'uses', 'atk_points1', 'def_points1', 'spi_points1', 'agi_points1', 'sp_cost', 'hit', 'critical_hit', 'skill_id', 'switch_id']:
                    row[key] = number(entity, key)
                for key in ['preemptive', 'dual_attack', 'attack_all', 'prevent_critical', 'half_sp_cost', 'use_skill']:
                    row[key] = entity.findtext(key) == 'T'
                row['description'] = entity.findtext('description') or ''
            elif kind == 'enemies':
                for key in ['max_hp', 'max_sp', 'attack', 'defense', 'spirit', 'agility', 'exp', 'gold']:
                    row[key] = number(entity, key)
            elif kind == 'skills':
                for key in ['type', 'sp_cost', 'power', 'hit', 'scope']:
                    row[key] = number(entity, key)
                row['description'] = entity.findtext('description') or ''
            rows.append(row)
        write_csv(output / (kind + '.csv'), rows, list(rows[0]))
    names = {kind: {x['id']: x['name'] for x in values} for kind, values in entities.items()}
    pages, dialogue, transfers, refs, maps = [], [], [], [], []
    histogram = collections.Counter()

    def reference(location, index, kind, ident, access, detail=''):
        refs.append(dict(location=location, command=index, kind=kind, id=ident,
                         name=names.get(kind, {}).get(ident, ''), access=access, detail=detail))

    def commands(container, location):
        result = []
        message = None
        for index, command in enumerate(container.findall('EventCommand'), 1):
            code = number(command, 'code')
            params = [int(x) for x in (command.findtext('parameters') or '').split()]
            string = command.findtext('string') or ''
            row = dict(index=index, code=code, name=codes.get(str(code), 'UNKNOWN'),
                       indent=number(command, 'indent'), parameters=params, text=string)
            result.append(row)
            histogram[code] += 1
            if code == 10110:
                message = dict(location=location, first_command=index, last_command=index, text=string)
                dialogue.append(message)
            elif code == 20110 and message is not None:
                message['text'] += '\n' + string
                message['last_command'] = index
            else:
                message = None
            if code == 10810 and len(params) >= 3:
                transfers.append(dict(location=location, command=index, target_map=params[0],
                                      target_name=map_infos.get(params[0], ET.Element('x')).findtext('name') or '',
                                      x=params[1], y=params[2], raw_parameters=json.dumps(params)))
            if code in [10210, 10220] and len(params) >= 4:
                kind = 'switches' if code == 10210 else 'variables'
                if params[0] in (0, 1):
                    lo, hi = params[1], params[1] if params[0] == 0 else params[2]
                    if not 0 < lo <= hi <= 100000:
                        raise ValueError('Unexpected state ID range')
                    for ident in range(lo, hi + 1):
                        reference(location, index, kind, ident, 'write', json.dumps(params))
                else:
                    reference(location, index, 'variables', params[1], 'indirect_target', json.dumps(params))
                if code == 10220 and len(params) >= 6 and params[4] in (1, 2):
                    reference(location, index, 'variables', params[5], 'read' if params[4] == 1 else 'indirect_read', json.dumps(params))
            if code == 12010 and len(params) >= 3:
                if params[0] in (0, 1):
                    kind = 'switches' if params[0] == 0 else 'variables'
                    reference(location, index, kind, params[1], 'branch_read', json.dumps(params))
                    if params[0] == 1 and len(params) >= 5 and params[2] == 1:
                        reference(location, index, 'variables', params[3], 'branch_operand_read', json.dumps(params))
                elif params[0] == 4:
                    reference(location, index, 'items', params[1], 'branch_read', json.dumps(params))
        return result

    for path in sorted(xml_dir.glob('Map*.emu')):
        mid = int(path.stem[3:])
        node = ET.parse(path).getroot().find('Map')
        info = map_infos.get(mid)
        mapname = info.findtext('name') if info is not None else ''
        events = node.findall('events/Event')
        page_count = 0
        for event in events:
            for page in event.findall('pages/EventPage'):
                page_count += 1
                location = f'Map{mid:04d}/Event{int(event.get("id")):04d}/Page{int(page.get("id")):04d}'
                cond = page.find('condition/EventPageCondition')
                condition = {}
                if cond is not None:
                    for flag in cond.find('flags/EventPageCondition_Flags'):
                        if flag.text == 'T':
                            key = {'switch_a': 'switch_a_id', 'switch_b': 'switch_b_id', 'variable': 'variable_id',
                                   'item': 'item_id', 'actor': 'actor_id', 'timer': 'timer_sec', 'timer2': 'timer2_sec'}[flag.tag]
                            ident = number(cond, key)
                            condition[flag.tag] = ident
                            kind = {'switch_a': 'switches', 'switch_b': 'switches', 'variable': 'variables', 'item': 'items', 'actor': 'actors'}.get(flag.tag)
                            if kind:
                                reference(location, 0, kind, ident, 'page_condition', json.dumps({'value': number(cond, 'variable_value'), 'operator': number(cond, 'compare_operator')}))
                    if 'variable' in condition:
                        condition.update(variable_value=number(cond, 'variable_value'), compare_operator=number(cond, 'compare_operator'))
                pages.append(dict(location=location, map_id=mid, map_name=mapname, event_name=event.findtext('name') or '',
                                  x=number(event, 'x'), y=number(event, 'y'), trigger=number(page, 'trigger'),
                                  condition=condition, commands=commands(page.find('event_commands'), location)))
        maps.append(dict(id=mid, name=mapname, parent=number(info, 'parent_map') if info is not None else None,
                         width=number(node, 'width'), height=number(node, 'height'), chipset=number(node, 'chipset_id'),
                         events=len(events), pages=page_count))
    for event in database.findall('commonevents/CommonEvent'):
        location = f'CommonEvent{int(event.get("id")):04d}'
        if event.findtext('switch_flag') == 'T':
            reference(location, 0, 'switches', number(event, 'switch_id'), 'common_event_condition')
        pages.append(dict(location=location, event_name=event.findtext('name') or '', trigger=number(event, 'trigger'),
                          condition={'switch': number(event, 'switch_id'), 'switch_flag': event.findtext('switch_flag')},
                          commands=commands(event.find('event_commands'), location)))
    for troop in database.findall('troops/Troop'):
        for page in troop.findall('pages/TroopPage'):
            location = f'Troop{int(troop.get("id")):04d}/Page{int(page.get("id")):04d}'
            cond = page.find('condition/TroopPageCondition')
            if cond is not None:
                flags = cond.find('flags/TroopPageCondition_Flags')
                for flag in ['switch_a', 'switch_b', 'variable']:
                    if flags is not None and flags.findtext(flag) == 'T':
                        reference(location, 0, 'variables' if flag == 'variable' else 'switches',
                                  number(cond, flag + '_id'), 'battle_page_condition')
            pages.append(dict(location=location, event_name=troop.findtext('name') or '',
                              condition={'raw_xml': ET.tostring(page.find('condition'), encoding='unicode')},
                              commands=commands(page.find('event_commands'), location)))
    write_csv(output / 'maps.csv', maps, list(maps[0]))
    write_csv(output / 'dialogue.csv', dialogue, ['location', 'first_command', 'last_command', 'text'])
    write_csv(output / 'map_transfers.csv', transfers, ['location', 'command', 'target_map', 'target_name', 'x', 'y', 'raw_parameters'])
    write_csv(output / 'state_references.csv', refs, ['location', 'command', 'kind', 'id', 'name', 'access', 'detail'])
    db_refs = []
    for kind, entry_tag in [('skills', 'Skill'), ('items', 'Item')]:
        for entry in database.findall(kind + '/' + entry_tag):
            fields = ['switch_id'] if kind == 'skills' and number(entry, 'type') == 3 else []
            if kind == 'items' and (number(entry, 'type') == 10 or entry.findtext('use_skill') == 'T'):
                fields += ['switch_id' if number(entry, 'type') == 10 else 'skill_id']
            for field in fields:
                db_refs.append(dict(kind=kind, id=int(entry.get('id')), name=entry.findtext('name') or '',
                                    field=field, target=number(entry, field)))
    write_csv(output / 'database_references.csv', db_refs, ['kind', 'id', 'name', 'field', 'target'])
    with (output / 'event_pages.jsonl').open('w', encoding='utf-8', newline='\n') as stream:
        for page in pages:
            stream.write(json.dumps(page, ensure_ascii=False, separators=(',', ':')) + '\n')
    unknown = {str(c): n for c, n in histogram.items() if str(c) not in codes}
    physical = {x['id'] for x in maps}
    missing_targets = sorted({x['target_map'] for x in transfers} - physical)
    default_source = (ROOT / 'original/game/仙剑奇侠传宿命篇').resolve()
    archive_reference = json.loads((ROOT / 'original/sample.json').read_text(encoding='utf-8'))['archive']['sha256'] if source == default_source else None
    summary = dict(sample_archive_reference_sha256=archive_reference, lcf_input_sha256=before,
                   input_count=len(inputs), xml_count=len(expected), encoding='CP936', engine_assumption='RM2003',
                   maps=len(maps), map_events=sum(x['events'] for x in maps), map_event_pages=sum(x['pages'] for x in maps),
                   indexed_pages=len(pages), commands=sum(histogram.values()), dialogue_blocks=len(dialogue), transfers=len(transfers),
                   state_references=len(refs), start=start, database_slots={k: len(v) for k, v in entities.items()},
                   named_database_rows={k: sum(bool(x['name'].strip()) and set(x['name'].strip()) != {'-'} for x in v) for k, v in entities.items()},
                   unknown_codes=unknown, missing_transfer_targets=missing_targets,
                   command_counts={str(k): v for k, v in sorted(histogram.items())},
                   scope_limits=['Static index, not a runtime validation or execution order',
                                 'State references cover page conditions, control commands and switch/variable/item branches; indirect and other command operands remain raw',
                                 'LCF2XML is not a decompiler of the RPG_RT executable'])
    if converter:
        summary['converter_sha256'] = sha256(converter)
    else:
        summary['converter_sha256'] = None
    if before != {p.name: sha256(p) for p in inputs}:
        raise RuntimeError('Original input bytes changed')
    summary['original_inputs_unchanged'] = True
    text = json.dumps(summary, ensure_ascii=False, indent=2) + '\n'
    (output / 'summary.json').write_text(text, encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'original/game/仙剑奇侠传宿命篇')
    parser.add_argument('--output', type=Path, default=ROOT / 'research/suming')
    parser.add_argument('--xml-dir', type=Path, default=ROOT / 'work/lcf-export/xml')
    parser.add_argument('--converter', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.source, args.output, args.xml_dir, args.converter)
    print(json.dumps({k: result[k] for k in ['maps', 'map_events', 'commands', 'dialogue_blocks', 'unknown_codes', 'missing_transfer_targets']}, ensure_ascii=False))
