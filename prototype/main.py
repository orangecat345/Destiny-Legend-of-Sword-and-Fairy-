from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--self-test', type=Path, help='Render and exercise the prototype without opening a window')
args = parser.parse_args()
if args.self_test:
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from core import Game

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
SCENARIO = json.loads((BASE / 'data/scenario.json').read_text(encoding='utf-8'))
W, H, TILE = 1280, 800, 32
MAP_X, MAP_Y = 32, 142
BG, PANEL, GOLD, JADE, TEXT, MUTED = '#0b151e', '#12222c', '#d8ba78', '#7dd9ce', '#e4e8df', '#91a7aa'


class View:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption('天问 · 回响之门 | 规则试作')
        self.fonts = {}
        candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc',
                      Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
        self.font_path = next((str(p) for p in candidates if p.exists()), None)
        self.buttons = []

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pygame.font.Font(self.font_path, size)
        return self.fonts[size]

    def text(self, text, pos, size=20, color=TEXT):
        self.screen.blit(self.font(size).render(str(text), True, color), pos)

    def wrap(self, text, rect, size=18, color=TEXT, gap=6, max_lines=20):
        font = self.font(size)
        lines, line = [], ''
        for char in str(text):
            if char == '\n' or font.size(line + char)[0] > rect.width:
                lines.append(line)
                line = '' if char == '\n' else char
            else:
                line += char
        if line:
            lines.append(line)
        for i, line in enumerate(lines[:max_lines]):
            self.text(line, (rect.x, rect.y + i * (size + gap)), size, color)
        return len(lines[:max_lines]) * (size + gap)

    def panel(self, rect, color=PANEL, border='#29434b'):
        pygame.draw.rect(self.screen, color, rect, border_radius=12)
        pygame.draw.rect(self.screen, border, rect, width=1, border_radius=12)

    def bar(self, label, value, maximum, pos, width=280, color=JADE):
        x, y = pos
        self.text(label, (x, y), 16, MUTED)
        self.text(f'{value} / {maximum}', (x + width - 90, y), 16, TEXT)
        pygame.draw.rect(self.screen, '#233943', (x, y + 28, width, 5), border_radius=3)
        pygame.draw.rect(self.screen, color, (x, y + 28, max(0, round(width * value / maximum)), 5), border_radius=3)

    def button(self, label, rect, action, enabled=True, accent=False):
        hover = rect.collidepoint(pygame.mouse.get_pos()) and not args.self_test
        fill = '#31534f' if hover and enabled else '#1b343c'
        if not enabled:
            fill = '#15252d'
        self.panel(rect, fill, GOLD if accent and enabled else '#36545b')
        rendered = self.font(19).render(label, True, GOLD if accent and enabled else TEXT if enabled else '#60747a')
        self.screen.blit(rendered, rendered.get_rect(center=rect.center))
        self.buttons.append((rect, action, enabled))

    def warrior(self, center, scale=1, shadow=False):
        x, y = center
        s = scale
        ink = '#17232c' if shadow else '#315b66'
        trim = '#9a7a9e' if shadow else JADE
        pygame.draw.ellipse(self.screen, '#07111a', (x-13*s, y+9*s, 28*s, 9*s))
        pygame.draw.polygon(self.screen, ink, [(x, y-12*s), (x-12*s, y+15*s), (x+12*s, y+15*s)])
        pygame.draw.line(self.screen, trim, (x, y-7*s), (x-4*s, y+10*s), max(1, s))
        pygame.draw.circle(self.screen, '#151f28', (x, y-15*s), 7*s)
        pygame.draw.circle(self.screen, '#978b7b' if shadow else '#d8bda1', (x, y-14*s), 5*s)
        pygame.draw.line(self.screen, '#c4c7ba', (x+8*s, y+7*s), (x+17*s, y-13*s), max(1, s))
        pygame.draw.line(self.screen, trim, (x-4*s, y-12*s), (x-17*s, y-8*s), max(1, s))

    def draw(self, game, ticks=0):
        self.buttons = []
        self.screen.fill(BG)
        for y in range(H):
            pygame.draw.line(self.screen, (11 + y//180, 21 + y//90, 30 + y//75), (0, y), (W, y))
        self.text('TIANWEN  /  PLAYABLE STUDY', (34, 22), 15, MUTED)
        self.text('天 问', (31, 42), 48, GOLD)
        self.text('回响之门', (222, 60), 28, TEXT)
        self.text('新增场景 · 规则试作 01', (34, 106), 16, MUTED)
        self.text('循迹  /  交锋  /  抉择', (918, 63), 24, GOLD)
        pygame.draw.line(self.screen, '#334850', (33, 127), (1247, 127))
        self.draw_map(game, ticks)
        self.draw_sidebar(game)
        mode = game.state.mode
        if mode == 'battle':
            self.draw_battle(game)
        elif mode in ('choice', 'ending', 'defeat'):
            self.draw_modal(game)
        self.panel(pygame.Rect(32, 704, 832, 58), '#14262f')
        self.wrap(game.log[-1], pygame.Rect(49, 716, 798, 44), 17, TEXT, 2, 2)
        self.text('WASD / 方向键 移动   E 交互   F5 存档   F9 读取   Esc 退出', (34, 776), 14, MUTED)
        pygame.display.flip()

    def draw_map(self, game, ticks):
        s = game.state
        grid = game.scenario['map']
        for y, row in enumerate(grid):
            for x, tile in enumerate(row):
                rect = pygame.Rect(MAP_X+x*TILE, MAP_Y+y*TILE, TILE, TILE)
                if tile == '#':
                    if 7 <= y <= 9 and 0 < x < 25:
                        pygame.draw.rect(self.screen, '#132c3c', rect)
                        for i in range(2):
                            offset = int(math.sin(ticks/1300 + x + i)*4)
                            pygame.draw.line(self.screen, '#204354', (rect.x+5+offset, rect.y+9+i*13), (rect.x+21+offset, rect.y+9+i*13))
                    else:
                        pygame.draw.rect(self.screen, '#20343d', rect)
                        pygame.draw.line(self.screen, '#35505a', rect.topleft, rect.topright)
                        pygame.draw.rect(self.screen, '#192b34', rect.inflate(-5, -8), border_radius=2)
                else:
                    pygame.draw.rect(self.screen, '#293c42' if (x+y)%2 else '#2b3f44', rect)
                    pygame.draw.rect(self.screen, '#25383d', rect, width=1)
                    if (x*7+y*13)%17 == 0:
                        pygame.draw.line(self.screen, '#41514e', (rect.x+5,rect.y+6), (rect.x+17,rect.y+24))
        # Two stone bridges span the water.
        for x in [6,7,17,18]:
            for y in [7,8,9]:
                rect=pygame.Rect(MAP_X+x*TILE, MAP_Y+y*TILE,TILE,TILE)
                pygame.draw.rect(self.screen, '#637373', rect.inflate(-2,-1))
                pygame.draw.line(self.screen, '#84918a', rect.topleft, rect.topright)
        for obj in game.scenario['objects']:
            x, y = MAP_X+obj['x']*TILE+16, MAP_Y+obj['y']*TILE+16
            if obj['kind'] == 'memory':
                active = obj['id'] not in s.collected
                color = GOLD if active else '#526a67'
                if active:
                    radius=18+int(math.sin(ticks/500+obj['x'])*2)
                    pygame.draw.circle(self.screen, '#4a5140',(x,y),radius,1)
                pygame.draw.rect(self.screen, '#415453', (x-8,y-13,16,24),border_radius=4)
                pygame.draw.line(self.screen,color,(x,y-7),(x,y+6),2)
                self.text(obj['label'],(x-16,y+20),15,color)
            elif obj['kind']=='gate':
                color=JADE if s.guard_defeated else '#7f8f89'
                pygame.draw.arc(self.screen,color,(x-23,y-29,46,49),0,math.pi,4)
                pygame.draw.line(self.screen,color,(x-23,y-5),(x-23,y+18),4)
                pygame.draw.line(self.screen,color,(x+22,y-5),(x+22,y+18),4)
                self.text('回响之门',(x-40,y+23),15,color)
            else:
                self.warrior((x,y),shadow=obj['kind']=='guard')
                self.text('已破' if obj['kind']=='guard' and s.guard_defeated else obj['label'],(x-25,y+21),15,MUTED)
        self.warrior((MAP_X+s.x*TILE+16, MAP_Y+s.y*TILE+16))
        pygame.draw.rect(self.screen,'#536a6b',pygame.Rect(32,142,832,544),1,8)
        obj=game.nearby()
        if obj and s.mode=='explore':
            self.panel(pygame.Rect(338,646,222,30),'#152a33',GOLD)
            self.text('E  '+obj['label'],(355,650),16,GOLD)

    def draw_sidebar(self, game):
        s=game.state
        self.panel(pygame.Rect(888,142,360,620))
        self.text('李剑灵', (914,165),27,TEXT)
        self.text('回响试炼', (1092,174),16,MUTED)
        self.bar('气血',s.hp,228,(914,212),308)
        self.bar('灵力',s.mp,39,(914,268),308,'#80a9dc')
        pygame.draw.line(self.screen,'#30464e',(914,323),(1222,323))
        self.text('留存回响', (914,343),19,GOLD)
        for i in range(3):
            pygame.draw.circle(self.screen,JADE if i<s.memory else '#30454b',(1105+i*36,356),8,0 if i<s.memory else 1)
        goals=[('寻回三枚碑文',len(s.collected)==3),('击散门前守影',s.guard_defeated),('选择如何继续前行',s.mode=='ending')]
        for i,(title,done) in enumerate(goals):
            y=394+i*38
            pygame.draw.circle(self.screen,JADE if done else '#647c7e',(922,y+11),5,0 if done else 1)
            self.text(title,(941,y),18,JADE if done else TEXT)
        pygame.draw.line(self.screen,'#30464e',(914,517),(1222,517))
        self.text('行 迹', (914,534),16,GOLD)
        y=565
        for line in game.log[-3:]:
            y+=self.wrap(line,pygame.Rect(914,y,307,55),15,MUTED,4,2)+10
        if s.mode=='battle':
            self.text('下一击：'+('蓄力重击 · 建议守势' if game.incoming()==66 else '普通斩击'),(914,724),16,GOLD)
        else:
            self.text('原型场景 · 非原作者剧本', (914,724),15,MUTED)

    def dim_map(self):
        shade=pygame.Surface((832,544),pygame.SRCALPHA);shade.fill((5,15,24,225))
        self.screen.blit(shade,(32,142))

    def draw_battle(self, game):
        self.dim_map();s=game.state
        self.text('回 响 交 锋', (330,178),32,GOLD)
        self.text('守住记忆，也为每一次逆转付出代价。',(242,232),19,MUTED)
        pygame.draw.ellipse(self.screen,'#1d3c43',(138,413,245,46),2)
        pygame.draw.ellipse(self.screen,'#3b3048',(522,413,245,46),2)
        self.warrior((255,379),4)
        self.warrior((640,379),4,True)
        self.text('李剑灵',(218,466),24,TEXT)
        self.text('守影',(618,466),24,TEXT)
        self.bar('气血',s.hp,228,(151,505),210)
        self.bar('守影',s.enemy_hp,144,(535,505),210,'#b798c5')
        labels=[('1  挥刀','attack',True),('2  御刀 · 5灵力','skill',s.mp>=5),('3  守势','defend',True),('4  回溯 · 1回响','rewind',s.memory>0 and s.previous_turn is not None)]
        for i,(label,action,enabled) in enumerate(labels):
            self.button(label,pygame.Rect(54+i*200,575,188,58),action,enabled,action=='skill')
        self.text('第 '+str(s.turn+1)+' 轮  /  '+('对手正蓄力，守势可化解重击' if game.incoming()==66 else '对手架势平稳'),(195,653),18,GOLD)

    def draw_modal(self, game):
        self.dim_map();s=game.state
        if s.mode=='choice':
            self.text('门后的路，由你选择',(259,227),32,GOLD)
            self.wrap('你已击散守影。带着尚存的回响上路，或把完整记忆封存在此，都是这场试炼留下的答案。',pygame.Rect(154,302,588,110),23,TEXT,14)
            self.button('1  携痕前行',pygame.Rect(154,463,264,64),'carry',accent=True)
            self.button('2  守住旧约',pygame.Rect(446,463,264,64),'seal',s.memory==3)
            self.text('守住旧约需要保有全部三枚回响',(263,565),18,MUTED)
        elif s.mode=='ending':
            ending=game.scenario['endings'][s.ending]
            self.text('试 炼 终 章',(345,211),20,MUTED)
            self.text(ending['title'],(307,267),47,GOLD)
            self.wrap(ending['text'],pygame.Rect(158,367,588,140),23,TEXT,14)
            self.button('R  再走一次',pygame.Rect(294,565,308,58),'restart',accent=True)
            self.text('本次新增试作结尾 · 不代表原作者续作剧情',(221,649),17,MUTED)
        else:
            self.text('此 路 暂 歇',(307,273),42,GOLD)
            self.wrap('守影尚未散去。留意对手每三轮一次的蓄力；守势可以恢复灵力，并显著减轻伤害。',pygame.Rect(165,371,570,110),22,TEXT,13)
            self.button('R  整备重试',pygame.Rect(294,565,308,58),'retry',accent=True)


def smoke(view, directory):
    directory.mkdir(parents=True,exist_ok=True)
    game=Game(SCENARIO)
    view.draw(game);pygame.image.save(view.screen,str(directory/'explore.png'))
    for obj in SCENARIO['objects']:
        if obj['kind']=='memory':
            game.state.x,game.state.y=obj['x'],obj['y'];game.interact()
    guard=next(x for x in SCENARIO['objects'] if x['kind']=='guard')
    game.state.x,game.state.y=guard['x'],guard['y'];game.interact();game.act('attack')
    assert game.state.mode=='battle'
    view.draw(game);pygame.image.save(view.screen,str(directory/'battle.png'))
    game.save(directory/'test-save.json')
    loaded=Game.load(SCENARIO,directory/'test-save.json');assert loaded.state==game.state
    while game.state.mode=='battle':game.act('skill')
    gate=next(x for x in SCENARIO['objects'] if x['kind']=='gate')
    game.state.x,game.state.y=gate['x'],gate['y'];game.interact()
    assert game.choose('seal')
    view.draw(game);pygame.image.save(view.screen,str(directory/'ending.png'))
    (directory/'result.json').write_text(json.dumps({'passed':True,'ending':game.state.ending,'roundtrip_save':True,'screenshots':3}),encoding='utf-8')
    pygame.quit()


def run(view):
    game=Game(SCENARIO);clock=pygame.time.Clock();running=True;next_move=0
    save=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TianwenPrototype/save.json'
    def action(name):
        nonlocal game,running
        if name=='restart':game=Game(SCENARIO)
        elif name=='retry':game.retry()
        elif game.state.mode=='battle':game.act(name)
        elif game.state.mode=='choice':game.choose(name)
    while running:
        ticks=pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type==pygame.QUIT:running=False
            elif event.type==pygame.KEYDOWN:
                if event.key==pygame.K_ESCAPE:running=False
                elif event.key==pygame.K_e:game.interact()
                elif event.key==pygame.K_r and game.state.mode in ['ending','defeat']:action('restart' if game.state.mode=='ending' else 'retry')
                elif event.key==pygame.K_F5:
                    try:game.save(save);game.tell('已保存当前进度。')
                    except OSError:game.tell('存档失败，请检查保存目录是否可写。')
                elif event.key==pygame.K_F9:
                    try:game=Game.load(SCENARIO,save)
                    except (OSError,ValueError,TypeError,KeyError):game.tell('未找到有效存档，当前进度已保留。')
                elif event.key in [pygame.K_1,pygame.K_2,pygame.K_3,pygame.K_4]:
                    index=event.key-pygame.K_1
                    action((['attack','skill','defend','rewind'] if game.state.mode=='battle' else ['carry','seal','',''])[index])
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                for rect,name,enabled in view.buttons:
                    if enabled and rect.collidepoint(event.pos):action(name);break
        if ticks>=next_move and game.state.mode=='explore':
            keys=pygame.key.get_pressed()
            for key,dx,dy in [(pygame.K_w,0,-1),(pygame.K_UP,0,-1),(pygame.K_s,0,1),(pygame.K_DOWN,0,1),(pygame.K_a,-1,0),(pygame.K_LEFT,-1,0),(pygame.K_d,1,0),(pygame.K_RIGHT,1,0)]:
                if keys[key]:game.move(dx,dy);next_move=ticks+135;break
        view.draw(game,ticks);clock.tick(60)
    pygame.quit()


if __name__=='__main__':
    view=View()
    if args.self_test:smoke(view,args.self_test)
    else:run(view)
