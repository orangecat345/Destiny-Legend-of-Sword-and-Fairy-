import json
from collections import deque
from dataclasses import asdict
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Game

SCENARIO = json.loads((Path(__file__).resolve().parents[1] / 'data/scenario.json').read_text(encoding='utf-8'))


def reach(game, obj):
    start = (game.state.x, game.state.y)
    target = (obj['x'], obj['y'])
    queue, paths = deque([start]), {start: []}
    while queue:
        pos = queue.popleft()
        if pos == target:
            for dx, dy in paths[pos]:
                assert game.move(dx, dy)
            return
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nxt = (pos[0] + dx, pos[1] + dy)
            if nxt not in paths and game.walkable(*nxt):
                paths[nxt] = paths[pos] + [(dx, dy)]
                queue.append(nxt)
    raise AssertionError('Unreachable scene object: ' + obj['id'])


def enter_battle():
    game = Game(SCENARIO)
    for obj in SCENARIO['objects']:
        if obj['kind'] == 'memory':
            reach(game, obj)
            game.interact()
    reach(game, next(x for x in SCENARIO['objects'] if x['kind'] == 'guard'))
    game.interact()
    assert game.state.mode == 'battle'
    return game


@pytest.mark.parametrize('ending', ['carry', 'seal'])
def test_reachable_full_playthrough_and_save(tmp_path, ending):
    game = enter_battle()
    assert not game.move(1, 0)
    while game.state.mode == 'battle':
        game.act('skill')
    reach(game, next(x for x in SCENARIO['objects'] if x['kind'] == 'gate'))
    game.interact()
    assert game.choose(ending)
    game.save(tmp_path / 'save.json')
    assert Game.load(SCENARIO, tmp_path / 'save.json').state == game.state


def test_rewind_keeps_its_cost_and_cannot_duplicate(tmp_path):
    game = enter_battle()
    before = (game.state.hp, game.state.mp, game.state.enemy_hp)
    game.act('skill')
    game.save(tmp_path / 'save.json')
    game = Game.load(SCENARIO, tmp_path / 'save.json')
    assert game.act('rewind')
    assert (game.state.hp, game.state.mp, game.state.enemy_hp) == before
    assert game.state.memory == 2
    assert not game.act('rewind')
    while game.state.mode == 'battle':
        game.act('skill')
    reach(game, next(x for x in SCENARIO['objects'] if x['kind'] == 'gate'))
    game.interact()
    assert not game.choose('seal')
    assert game.choose('carry')


def test_gates_defeat_retry_and_insufficient_mp():
    game = Game(SCENARIO)
    reach(game, next(x for x in SCENARIO['objects'] if x['kind'] == 'gate'))
    game.interact()
    assert game.state.mode == 'explore'
    game = enter_battle()
    game.state.mp = 0
    snapshot = asdict(game.state)
    assert not game.act('skill')
    assert asdict(game.state) == snapshot
    game.state.hp = 1
    game.act('attack')
    assert game.state.mode == 'defeat'
    assert game.retry()
    assert game.state.hp == 228 and len(game.state.collected) == 3


def test_reject_corrupt_save_without_mutating_game(tmp_path):
    game = Game(SCENARIO)
    game.save(tmp_path / 'save.json')
    raw = json.loads((tmp_path / 'save.json').read_text(encoding='utf-8'))
    raw['collected'] = ['echo_north', 'echo_north']
    (tmp_path / 'save.json').write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError):
        Game.load(SCENARIO, tmp_path / 'save.json')
    assert not game.state.collected
    raw['collected'] = []
    raw['mode'] = 'ending'
    raw['guard_defeated'] = True
    (tmp_path / 'save.json').write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError):
        Game.load(SCENARIO, tmp_path / 'save.json')
