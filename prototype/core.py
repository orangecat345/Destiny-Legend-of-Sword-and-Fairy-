"""Deterministic gameplay experiment; scene and combat rules are new design."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import tempfile
import os


@dataclass
class State:
    version: int = 1
    x: int = 3
    y: int = 13
    hp: int = 228
    mp: int = 39
    collected: list[str] = field(default_factory=list)
    memory: int = 0
    guard_defeated: bool = False
    mode: str = 'explore'
    enemy_hp: int = 144
    turn: int = 0
    previous_turn: dict | None = None
    ending: str | None = None


class Game:
    def __init__(self, scenario: dict, state: State | None = None):
        self.scenario = scenario
        self.state = state or State()
        self.log = ['循着石径前行，寻找三枚回响。']

    def tell(self, text):
        self.log = (self.log + [text])[-6:]
        return text

    def walkable(self, x, y):
        grid = self.scenario['map']
        return 0 <= y < len(grid) and 0 <= x < len(grid[0]) and grid[y][x] != '#'

    def move(self, dx, dy):
        s = self.state
        if s.mode != 'explore' or abs(dx) + abs(dy) != 1:
            return False
        if self.walkable(s.x + dx, s.y + dy):
            s.x += dx
            s.y += dy
            return True
        return False

    def nearby(self):
        s = self.state
        choices = []
        for obj in self.scenario['objects']:
            if obj['id'] in s.collected:
                continue
            distance = abs(obj['x'] - s.x) + abs(obj['y'] - s.y)
            if distance <= 1:
                choices.append((distance, obj['id'], obj))
        return min(choices, default=(0, '', None))[2]

    def interact(self):
        s = self.state
        if s.mode != 'explore':
            return
        obj = self.nearby()
        if not obj:
            return self.tell('靠近石碑、守碑人或回响之门，按 E 交互。')
        if obj['kind'] == 'memory':
            s.collected.append(obj['id'])
            s.memory += 1
            return self.tell(obj['text'])
        if obj['kind'] == 'guide':
            return self.tell('守碑人：三枚回响能开此门；但逆转一次战局，便会遗失一枚。')
        if obj['kind'] == 'guard':
            if s.guard_defeated:
                return self.tell('守影已经散去。北侧的回响之门仍在等待。')
            if len(s.collected) < 3:
                return self.tell('守影：回响尚未聚齐。请先寻遍三座石碑。')
            s.mode = 'battle'
            s.enemy_hp, s.turn, s.previous_turn = 144, 0, None
            return self.tell('守影凝形。它每三轮蓄力一次；留意架势，及时守势。')
        if obj['kind'] == 'gate':
            if not s.guard_defeated:
                return self.tell('回响之门尚被守影封锁。')
            s.mode = 'choice'
            return self.tell('门后没有既定答案。你愿如何带着这段记忆继续前行？')

    def incoming(self):
        return 66 if self.state.turn % 3 == 1 else 28

    def act(self, action):
        s = self.state
        if s.mode != 'battle':
            return False
        if action == 'rewind':
            if s.memory < 1 or s.previous_turn is None:
                self.tell('没有可回溯的上一轮，或回响已经耗尽。')
                return False
            for key, value in s.previous_turn.items():
                setattr(s, key, value)
            s.memory -= 1
            s.previous_turn = None
            self.tell('回溯上一轮。一枚回响随之淡去；这份代价不会倒流。')
            return True
        if action not in ('attack', 'skill', 'defend'):
            return False
        if action == 'skill' and s.mp < 5:
            self.tell('灵力不足，无法施展御刀术。')
            return False
        s.previous_turn = {key: getattr(s, key) for key in ['hp', 'mp', 'enemy_hp', 'turn']}
        incoming = self.incoming()
        if action == 'attack':
            s.enemy_hp = max(0, s.enemy_hp - 29)
            self.tell('刀光掠过，守影受到 29 点伤害。')
        elif action == 'skill':
            s.mp -= 5
            s.enemy_hp = max(0, s.enemy_hp - 50)
            self.tell('御刀术：消耗 5 点灵力，守影受到 50 点伤害。')
        else:
            s.mp = min(39, s.mp + 4)
            incoming = (incoming + 3) // 4
            self.tell('稳住守势，恢复 4 点灵力，大幅减轻本轮伤害。')
        s.turn += 1
        if s.enemy_hp == 0:
            s.guard_defeated = True
            s.mode = 'explore'
            s.previous_turn = None
            self.tell('守影散去。去往北侧的回响之门，作出你的选择。')
            return True
        s.hp = max(0, s.hp - incoming)
        self.tell(f'守影反击，造成 {incoming} 点伤害。')
        if s.hp == 0:
            s.mode = 'defeat'
            self.tell('此路暂歇。可以整备后重试；收集的碑文仍然保留。')
        return True

    def retry(self):
        if self.state.mode != 'defeat':
            return False
        s = self.state
        s.hp, s.mp, s.enemy_hp, s.turn = 228, 39, 144, 0
        s.mode, s.previous_turn = 'battle', None
        self.tell('再次迎向守影。留意第二轮的蓄力攻击。')
        return True

    def choose(self, ending):
        s = self.state
        if s.mode != 'choice' or ending not in ['carry', 'seal']:
            return False
        if ending == 'seal' and s.memory < 3:
            self.tell('封存完整记忆需要保有全部三枚回响。')
            return False
        s.ending, s.mode = ending, 'ending'
        self.tell(self.scenario['endings'][ending]['text'])
        return True

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix='.tianwen-', suffix='.json', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(asdict(self.state), stream, ensure_ascii=False, indent=2)
            os.replace(name, path)
        finally:
            if Path(name).exists():
                Path(name).unlink()

    @classmethod
    def load(cls, scenario: dict, path: Path):
        raw = json.loads(path.read_text(encoding='utf-8'))
        if set(raw) != set(State.__dataclass_fields__) or raw['version'] != 1:
            raise ValueError('存档格式或版本不兼容')
        ints = ['x', 'y', 'hp', 'mp', 'memory', 'enemy_hp', 'turn']
        if any(type(raw[k]) is not int for k in ints):
            raise ValueError('存档数值无效')
        if not isinstance(raw['collected'], list) or any(not isinstance(x, str) for x in raw['collected']):
            raise ValueError('存档回响数据无效')
        valid = {x['id'] for x in scenario['objects'] if x['kind'] == 'memory'}
        if len(set(raw['collected'])) != len(raw['collected']) or not set(raw['collected']) <= valid:
            raise ValueError('存档存在重复或未知回响')
        if not 0 <= raw['memory'] <= len(raw['collected']) <= 3 or not 0 <= raw['hp'] <= 228 or not 0 <= raw['mp'] <= 39:
            raise ValueError('存档数值超出范围')
        if raw['mode'] not in ['explore', 'battle', 'choice', 'ending', 'defeat'] or raw['ending'] not in [None, 'carry', 'seal']:
            raise ValueError('存档场景无效')
        if type(raw['guard_defeated']) is not bool or not 0 <= raw['enemy_hp'] <= 144 or raw['turn'] < 0:
            raise ValueError('存档战斗状态无效')
        prev = raw['previous_turn']
        if prev is not None:
            if not isinstance(prev, dict) or set(prev) != {'hp', 'mp', 'enemy_hp', 'turn'} or any(type(v) is not int for v in prev.values()):
                raise ValueError('存档回溯状态无效')
            if not 0 <= prev['hp'] <= 228 or not 0 <= prev['mp'] <= 39 or not 0 <= prev['enemy_hp'] <= 144 or prev['turn'] < 0:
                raise ValueError('存档回溯数值超出范围')
        game = cls(scenario, State(**raw))
        if not game.walkable(raw['x'], raw['y']):
            raise ValueError('存档坐标不可通行')
        if raw['mode'] in ['choice', 'ending'] and not raw['guard_defeated']:
            raise ValueError('存档缺少过门条件')
        if (raw['mode'] == 'ending') != (raw['ending'] is not None):
            raise ValueError('存档结尾状态不一致')
        if raw['ending'] == 'seal' and raw['memory'] != 3:
            raise ValueError('存档缺少完整回响')
        if raw['mode'] == 'defeat' and raw['hp'] != 0:
            raise ValueError('存档败退状态不一致')
        game.tell('已读取存档。')
        return game
