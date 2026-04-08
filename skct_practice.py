#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import time
import subprocess

TOTAL_QUESTIONS = 20
TIME_LIMIT      = 15 * 60
WARN_SECONDS    = 45

BG       = '#f0f0f0'
PANEL_BG = '#ffffff'
DARK     = '#1e2d3d'
MID      = '#777777'
ACCENT   = '#3a7bd5'
DANGER   = '#e74c3c'
BTN_BG   = '#e8e8e8'
DIVIDER  = '#d0d0d0'


# ─────────────────────────────────────────────
#  Label 기반 버튼 (다크모드에서도 색상 보장)
# ─────────────────────────────────────────────
class FlatBtn(tk.Label):
    """tk.Button은 macOS 다크모드에서 Aqua 렌더러가 색을 덮어씀.
    tk.Label은 bg/fg를 그대로 유지하므로 커스텀 버튼으로 사용."""
    def __init__(self, parent, text, bg, fg, command=None,
                 hover_bg=None, font=None, padx=8, pady=4, **kw):
        fnt = font or ('Apple SD Gothic Neo', 12)
        super().__init__(parent, text=text, bg=bg, fg=fg,
                         font=fnt, padx=padx, pady=pady,
                         cursor='hand2', relief='flat', **kw)
        self._bg = bg
        self._fg = fg
        self._hover = hover_bg or bg
        self._cmd   = command
        self._disabled = False

        self.bind('<Enter>',    lambda e: self._on_hover(True))
        self.bind('<Leave>',    lambda e: self._on_hover(False))
        self.bind('<Button-1>', lambda e: self._on_click())

    def _on_hover(self, entering):
        if self._disabled:
            return
        self.config(bg=self._hover if entering else self._bg)

    def _on_click(self):
        if not self._disabled and self._cmd:
            self._cmd()

    def set_colors(self, bg, fg):
        self._bg = bg
        self._fg = fg
        self.config(bg=bg, fg=fg)

    def set_disabled(self, disabled):
        self._disabled = disabled
        self.config(bg='#c0c8d0' if disabled else self._bg,
                    fg='#888888' if disabled else self._fg,
                    cursor='' if disabled else 'hand2')


# ─────────────────────────────────────────────
#  내장 메모장
# ─────────────────────────────────────────────
class NotepadPanel(tk.Frame):
    def __init__(self, parent, on_focus=None, calc_active_fn=None, calc_key_fn=None):
        super().__init__(parent, bg=PANEL_BG)
        self._on_focus       = on_focus
        self._calc_active_fn = calc_active_fn
        self._calc_key_fn    = calc_key_fn

        self._hdr = tk.Frame(self, bg='#e4e4e4')
        self._hdr.pack(fill='x')
        self._title = tk.Label(self._hdr, text='메모장',
                 font=('Apple SD Gothic Neo', 11, 'bold'),
                 bg='#e4e4e4', fg=DARK, padx=8, pady=5)
        self._title.pack(side='left')
        hdr = self._hdr
        FlatBtn(hdr, '지우기', bg='#d0d0d0', fg=DARK,
                hover_bg='#b8b8b8',
                font=('Apple SD Gothic Neo', 10), padx=8, pady=3,
                command=lambda: self.text.delete('1.0', 'end')
                ).pack(side='right', padx=4, pady=3)

        self.text = tk.Text(
            self, font=('Apple SD Gothic Neo', 12),
            bg=PANEL_BG, fg=DARK,
            insertbackground=DARK,
            relief='flat', bd=0, padx=8, pady=6,
            wrap='word', highlightthickness=0,
            selectbackground=ACCENT, selectforeground='white',
            undo=True,
        )
        sb = tk.Scrollbar(self, command=self.text.yview,
                          bg=BG, troughcolor=BG, relief='flat')
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.text.pack(fill='both', expand=True)

        self.text.bind('<FocusIn>',  lambda e: self.set_active(True))
        self.text.bind('<FocusOut>', lambda e: self.set_active(False))
        # 한글 IME Enter: 직접 줄바꿈 삽입 후 이벤트 차단
        self.text.bind('<Return>',   self._handle_return)
        self.text.bind('<KP_Enter>', self._handle_return)
        # 복붙 차단 (Cmd+C/V/X) - <Key> 전체 바인딩 없이 개별 처리
        for k in ('c', 'v', 'x', 'C', 'V', 'X'):
            self.text.bind(f'<Command-{k}>', lambda e: 'break')

    def _intercept(self, event):
        if self._calc_active_fn and self._calc_active_fn():
            if self._calc_key_fn:
                self._calc_key_fn(event)
            return 'break'
        # 계산기 비활성 시: 복붙만 차단
        if event.state & 0x8 and event.keysym in ('c', 'v', 'x', 'C', 'V', 'X'):
            return 'break'

    def _handle_return(self, event):
        # 계산기 활성 중이면 = 로 라우팅
        if self._calc_active_fn and self._calc_active_fn():
            if self._calc_key_fn:
                self._calc_key_fn(event)
            return 'break'
        self.text.insert('insert', '\n')
        return 'break'

    def set_active(self, active):
        bg = ACCENT if active else '#e4e4e4'
        fg = 'white' if active else DARK
        self._hdr.config(bg=bg)
        self._title.config(bg=bg, fg=fg)
        if active and self._on_focus:
            self._on_focus()

    def show_cursor(self, visible):
        self.text.config(insertwidth=2 if visible else 0)
        if visible:
            self.text.unbind('<Key>')
        else:
            self.text.bind('<Key>', self._intercept)

    def reset(self):
        self.text.delete('1.0', 'end')


# ─────────────────────────────────────────────
#  내장 그림판
# ─────────────────────────────────────────────
class DrawPanel(tk.Frame):
    def __init__(self, parent, on_focus=None):
        super().__init__(parent, bg=PANEL_BG)
        self._color    = 'black'
        self._last     = (None, None)
        self._size     = tk.IntVar(value=3)
        self._on_focus = on_focus

        self._hdr = tk.Frame(self, bg='#e4e4e4')
        self._hdr.pack(fill='x')
        self._title = tk.Label(self._hdr, text='그림판',
                 font=('Apple SD Gothic Neo', 11, 'bold'),
                 bg='#e4e4e4', fg=DARK, padx=8, pady=5)
        self._title.pack(side='left')
        hdr = self._hdr

        for c, label in [('black','검'), ('red','빨'), ('blue','파'),
                          ('green','초'), ('white','지우개')]:
            FlatBtn(hdr, label, bg='#d0d0d0',
                    fg=c if c != 'white' else DARK,
                    hover_bg='#b8b8b8',
                    font=('Apple SD Gothic Neo', 10), padx=5, pady=3,
                    command=lambda col=c: setattr(self, '_color', col)
                    ).pack(side='right', padx=1, pady=3)

        tk.Spinbox(hdr, from_=1, to=20, textvariable=self._size,
                   width=3, bg='#e4e4e4', fg=DARK,
                   buttonbackground='#d0d0d0', relief='flat'
                   ).pack(side='right', padx=2, pady=4)
        tk.Label(hdr, text='굵기', bg='#e4e4e4', fg=DARK,
                 font=('Apple SD Gothic Neo', 10)).pack(side='right')

        FlatBtn(hdr, '지우기', bg='#d0d0d0', fg=DARK,
                hover_bg='#b8b8b8',
                font=('Apple SD Gothic Neo', 10), padx=8, pady=3,
                command=lambda: self.canvas.delete('all')
                ).pack(side='left', padx=4, pady=3)

        self.canvas = tk.Canvas(self, bg='white', cursor='crosshair',
                                highlightthickness=1, highlightbackground='#d0d0d0')
        self.canvas.pack(fill='both', expand=True, padx=2, pady=2)
        self.canvas.bind('<Button-1>',     self._on_click)
        self.canvas.bind('<B1-Motion>',    self._draw)
        self.canvas.bind('<ButtonRelease-1>',
                         lambda e: setattr(self, '_last', (None, None)))

    def _on_click(self, e):
        self.canvas.focus_set()
        if self._on_focus:
            self._on_focus()
        self.set_active(True)

    def _draw(self, e):
        lx, ly = self._last
        if lx is not None:
            self.canvas.create_line(lx, ly, e.x, e.y,
                                    fill=self._color, width=self._size.get(),
                                    capstyle='round', smooth=True)
        self._last = (e.x, e.y)

    def set_active(self, active):
        bg = ACCENT if active else '#e4e4e4'
        fg = 'white' if active else DARK
        self._hdr.config(bg=bg)
        self._title.config(bg=bg, fg=fg)

    def reset(self):
        self.canvas.delete('all')


# ─────────────────────────────────────────────
#  내장 계산기  (키보드 입력 지원)
# ─────────────────────────────────────────────
class CalcPanel(tk.Frame):
    def __init__(self, parent, on_activate=None):
        super().__init__(parent, bg=PANEL_BG)
        self._expr       = ''
        self._on_activate = on_activate  # 계산기 클릭 시 호출 (상태 플래그 세팅용)

        self._hdr = tk.Frame(self, bg='#e4e4e4')
        self._hdr.pack(fill='x')
        self._title = tk.Label(self._hdr, text='계산기  (클릭 후 키보드 입력 가능)',
                 font=('Apple SD Gothic Neo', 10, 'bold'),
                 bg='#e4e4e4', fg=DARK, padx=8, pady=5)
        self._title.pack(side='left')
        self._hdr.bind('<Button-1>', self._clicked)

        self.display = tk.Label(
            self, text='0', anchor='e',
            font=('Menlo', 18, 'bold'),
            bg='#e0e0e0', fg=DARK,
            padx=10, pady=8, relief='flat',
            highlightthickness=2,
            highlightbackground='#e0e0e0',
            highlightcolor='#e0e0e0'
        )
        self.display.pack(fill='x', padx=8, pady=(5, 3))
        self.display.bind('<Button-1>', self._clicked)

        btn_grid = tk.Frame(self, bg=PANEL_BG)
        btn_grid.pack(fill='x', padx=8, pady=(2, 4))
        for c in range(4):
            btn_grid.columnconfigure(c, weight=1, uniform='calc')

        layout = [
            ('C',   '#c8c8c8', 0, 0, 1), ('+/-','#c8c8c8', 0, 1, 1),
            ('%',   '#c8c8c8', 0, 2, 1), ('÷',  ACCENT,    0, 3, 1),
            ('7',   BTN_BG,    1, 0, 1), ('8',  BTN_BG,    1, 1, 1),
            ('9',   BTN_BG,    1, 2, 1), ('×',  ACCENT,    1, 3, 1),
            ('4',   BTN_BG,    2, 0, 1), ('5',  BTN_BG,    2, 1, 1),
            ('6',   BTN_BG,    2, 2, 1), ('−',  ACCENT,    2, 3, 1),
            ('1',   BTN_BG,    3, 0, 1), ('2',  BTN_BG,    3, 1, 1),
            ('3',   BTN_BG,    3, 2, 1), ('+',  ACCENT,    3, 3, 1),
            ('0',   BTN_BG,    4, 0, 2), ('.',  BTN_BG,    4, 2, 1),
            ('=',   ACCENT,    4, 3, 1),
        ]
        for key, bg, r, c, cs in layout:
            fg    = 'white' if bg == ACCENT else DARK
            hover = '#2962c4' if bg == ACCENT else '#d8d8d8'
            btn = FlatBtn(btn_grid, key, bg=bg, fg=fg, hover_bg=hover,
                          font=('Apple SD Gothic Neo', 13, 'bold'),
                          padx=0, pady=7,
                          command=lambda k=key: self.press(k))
            btn.bind('<Button-1>', self._clicked, add='+')
            btn.grid(row=r, column=c, columnspan=cs,
                     sticky='nsew', padx=1, pady=1)

    def _clicked(self, *_):
        if self._on_activate:
            self._on_activate()
        self.set_active(True)

    def set_active(self, active):
        bg = ACCENT if active else '#e4e4e4'
        fg = 'white' if active else DARK
        self._hdr.config(bg=bg)
        self._title.config(bg=bg, fg=fg)
        color = ACCENT if active else '#e0e0e0'
        self.display.config(highlightbackground=color, highlightcolor=color)

    def _fmt(self, expr):
        """표시용: 수식에서 숫자 부분에만 세 자리 쉼표 적용"""
        import re
        parts = re.split(r'([÷×−+])', expr)
        out = []
        for p in parts:
            if p in '÷×−+':
                out.append(p)
            elif p == '':
                pass
            else:
                try:
                    if p.endswith('.'):
                        out.append(f'{int(p[:-1]):,}.')
                    elif '.' in p:
                        i, d = p.split('.', 1)
                        out.append(f'{int(i):,}.{d}' if i else f'.{d}')
                    else:
                        out.append(f'{int(p):,}')
                except ValueError:
                    out.append(p)
        return ''.join(out) or '0'

    def _show(self, fallback='0'):
        self.display.config(text=self._fmt(self._expr) if self._expr else fallback)

    def reset(self):
        self._expr = ''
        self.display.config(text='0')
        self.set_active(False)

    def press(self, key):
        if key == 'C':
            self._expr = ''
            self.display.config(text='0')
        elif key == 'BS':
            self._expr = self._expr[:-1]
            self._show()
        elif key == '=':
            try:
                expr = self._expr.replace('÷','/').replace('×','*').replace('−','-')
                r = eval(expr)
                if isinstance(r, float) and r.is_integer():
                    r = int(r)
                self._expr = str(r)
                self._show()
            except Exception:
                self.display.config(text='오류')
                self._expr = ''
        elif key == '+/-':
            try:
                v = eval(self._expr.replace('÷','/').replace('×','*').replace('−','-'))
                self._expr = str(-v)
                self._show()
            except Exception:
                pass
        elif key == '%':
            try:
                v = eval(self._expr.replace('÷','/').replace('×','*').replace('−','-'))
                self._expr = str(v / 100)
                self._show()
            except Exception:
                pass
        else:
            ops = set('÷×−+')
            if key in ops and self._expr and self._expr[-1] in ops:
                self._expr = self._expr[:-1] + key  # 연산부호 교체
            else:
                self._expr += key
            self._show()


# ─────────────────────────────────────────────
#  메인 앱
# ─────────────────────────────────────────────
class SKCTApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('SKCT 연습')
        self.root.geometry('1200x680')
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        # 다크모드 팔레트 고정
        self.root.tk_setPalette(
            background=BG, foreground=DARK,
            activeBackground='#dce8fb', activeForeground=DARK,
            highlightBackground=BG, highlightColor=ACCENT,
            selectBackground=ACCENT, selectForeground='white',
            insertBackground=DARK,
        )

        self._mode      = 'full'   # 'full' | 'single'
        self.current_q  = 0
        self._selected  = 0
        self.answers    = [None] * TOTAL_QUESTIONS
        self.times      = [0.0]  * TOTAL_QUESTIONS
        self.q_start    = None
        self.subj_start = None
        self.ticking    = False
        self._calc_ref    = None
        self._calc_active = False   # 계산기 키보드 모드 여부
        self._alarm_played = False

        self._build_ui()
        self._show_start_overlay()
        self.root.mainloop()

    def _build_ui(self):
        # ── 왼쪽 컨트롤 패널 ────────────────────────────────
        left = tk.Frame(self.root, bg=BG, width=210)
        left.pack(side='left', fill='y', padx=(14, 0), pady=14)
        left.pack_propagate(False)

        self.q_lbl = tk.Label(left, text='문제 1 / 20',
                              font=('Apple SD Gothic Neo', 15, 'bold'),
                              bg=BG, fg=DARK)
        self.q_lbl.pack(pady=(18, 2))

        self.timer_lbl = tk.Label(left, text='00:00',
                                  font=('Apple SD Gothic Neo', 48, 'bold'),
                                  bg=BG, fg=DARK)
        self.timer_lbl.pack()

        self.total_lbl = tk.Label(left, text='남은 시간  15:00',
                                  font=('Apple SD Gothic Neo', 10),
                                  bg=BG, fg=MID)
        self.total_lbl.pack(pady=(2, 14))

        # 답 선택 버튼 (세로, FlatBtn)
        ans_col = tk.Frame(left, bg=BG)
        ans_col.pack(fill='x', padx=14)
        self.ans_btns = []
        for i in range(1, 6):
            btn = FlatBtn(
                ans_col, str(i),
                bg=BTN_BG, fg=DARK,
                hover_bg='#dce8fb',
                font=('Apple SD Gothic Neo', 15, 'bold'),
                padx=0, pady=7,
                command=lambda a=i: self._select(a)
            )
            btn.pack(fill='x', pady=2)
            self.ans_btns.append(btn)

        # 다음 문제 버튼 (클릭 전용 - Enter 없음)
        self.next_btn = FlatBtn(
            left, '다음 문제  →',  # single 모드에서는 _begin_q()에서 텍스트 교체
            bg='#b0b8c1', fg='white',
            hover_bg='#2962c4',
            font=('Apple SD Gothic Neo', 12, 'bold'),
            padx=0, pady=9,
            command=self._advance
        )
        self.next_btn.set_disabled(True)
        self.next_btn.pack(fill='x', padx=14, pady=10)

        tk.Label(left, text='1~5: 답 선택',
                 font=('Apple SD Gothic Neo', 9),
                 bg=BG, fg='#aaaaaa').pack()

        # 답안 현황 인라인 표 (full 모드용)
        self.ans_grid_frame = tk.Frame(left, bg=BG)
        self.ans_grid_frame.pack(fill='x', padx=14, pady=(14, 0))
        self._ans_cells = []   # (q_lbl, ans_lbl, cell_frame) × 20
        for i in range(TOTAL_QUESTIONS):
            row, col = divmod(i, 5)
            cell = tk.Frame(self.ans_grid_frame, bg='#e0e0e0',
                            width=34, height=34)
            cell.grid(row=row, column=col, padx=1, pady=1)
            cell.pack_propagate(False)
            tk.Label(cell, text=f'{i+1}',
                     font=('Apple SD Gothic Neo', 7),
                     bg='#e0e0e0', fg=MID).pack(pady=(2, 0))
            ans_lbl = tk.Label(cell, text='-',
                               font=('Apple SD Gothic Neo', 11, 'bold'),
                               bg='#e0e0e0', fg='#aaaaaa')
            ans_lbl.pack()
            self._ans_cells.append((cell, ans_lbl))

        self.menu_btn = FlatBtn(left, '메인메뉴',
                bg='#e0e0e0', fg=DARK, hover_bg='#c8c8c8',
                font=('Apple SD Gothic Neo', 11),
                padx=0, pady=6,
                command=self._go_to_menu
                )

        # ── 루트 키 바인딩 (계산기/답 선택 모두 여기서 처리) ──
        for i in range(10):
            self.root.bind(str(i), lambda e, n=str(i): self._kb_digit(e, n))
            self.root.bind(f'<KP_{i}>', lambda e, n=str(i): self._kb_digit(e, n))
        for ch in '.+':
            self.root.bind(ch, lambda e, c=ch: self._kb_calc(e, c))
        for src, dst in [('*','×'),('/','÷'),('-','−'),('=','=')]:
            self.root.bind(src, lambda e, d=dst: self._kb_calc(e, d))
        self.root.bind('<BackSpace>', lambda e: self._kb_calc(e, 'BS'))
        self.root.bind('c',          lambda e: self._kb_calc(e, 'C'))
        self.root.bind('C',          lambda e: self._kb_calc(e, 'C'))
        self.root.bind('<KP_Decimal>',  lambda e: self._kb_calc(e, '.'))
        self.root.bind('<KP_Add>',      lambda e: self._kb_calc(e, '+'))
        self.root.bind('<KP_Subtract>', lambda e: self._kb_calc(e, '−'))
        self.root.bind('<KP_Multiply>', lambda e: self._kb_calc(e, '×'))
        self.root.bind('<KP_Divide>',   lambda e: self._kb_calc(e, '÷'))
        self.root.bind('<KP_Enter>',    lambda e: self._kb_calc(e, '='))
        self.root.bind('<Return>',      lambda e: self._kb_calc(e, '='))

        # 메모장 / 그림판 클릭 → 계산기 비활성화
        self.root.bind('<Button-1>', self._on_root_click, add='+')

        # ── 구분선 ───────────────────────────────────────────
        tk.Frame(self.root, bg=DIVIDER, width=1).pack(
            side='left', fill='y', pady=14)

        # ── 오른쪽 도구 영역 ─────────────────────────────────
        pane_h = tk.PanedWindow(self.root, orient='horizontal',
                                bg=DIVIDER, sashwidth=5,
                                sashrelief='flat', sashpad=0)
        pane_h.pack(side='left', fill='both', expand=True,
                    padx=(0, 14), pady=14)

        self._memo_panel = NotepadPanel(pane_h, on_focus=lambda: [self._deactivate_calc(),
                                                                   self._draw_panel.set_active(False)],
                                         calc_active_fn=lambda: self._calc_active,
                                         calc_key_fn=self._route_key_to_calc)
        pane_h.add(self._memo_panel, minsize=200, stretch='always')

        pane_v = tk.PanedWindow(pane_h, orient='vertical',
                                bg=DIVIDER, sashwidth=5,
                                sashrelief='flat', sashpad=0)
        pane_h.add(pane_v, minsize=200, stretch='always')

        self._draw_panel = DrawPanel(pane_v,
                                     on_focus=lambda: [self._deactivate_calc(),
                                                       self._memo_panel.set_active(False)])
        pane_v.add(self._draw_panel, minsize=120, stretch='always')

        self._calc_ref = CalcPanel(pane_v, on_activate=self._activate_calc)
        pane_v.add(self._calc_ref, minsize=260, stretch='never')

        self.root.after(100, lambda: pane_h.sash_place(0, 470, 0))

    def _activate_calc(self):
        self._calc_active = True
        self._calc_ref.set_active(True)
        self._memo_panel.set_active(False)
        self._memo_panel.show_cursor(False)
        self._draw_panel.set_active(False)

    def _deactivate_calc(self):
        self._calc_active = False
        if self._calc_ref:
            self._calc_ref.set_active(False)
        self._memo_panel.show_cursor(True)

    def _on_root_click(self, event):
        # 계산기 위젯이 아닌 곳 클릭 시 계산기 비활성화
        w = event.widget
        if self._calc_ref and (w is self._calc_ref or
                               str(w).startswith(str(self._calc_ref))):
            return  # 계산기 내부 클릭 → 유지
        self._deactivate_calc()

    # ── 시작 오버레이 ─────────────────────────────────────────

    def _show_start_overlay(self):
        self._overlay = tk.Frame(self.root, bg=BG)
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.root.focus_set()

        inner = tk.Frame(self._overlay, bg=BG)
        inner.place(relx=0.5, rely=0.5, anchor='center')

        tk.Label(inner, text='SKCT 연습',
                 font=('Apple SD Gothic Neo', 28, 'bold'),
                 bg=BG, fg=DARK).pack(pady=(0, 8))
        tk.Label(inner, text='모드를 선택하세요',
                 font=('Apple SD Gothic Neo', 13),
                 bg=BG, fg=MID).pack(pady=(0, 28))

        btn_frame = tk.Frame(inner, bg=BG)
        btn_frame.pack()

        # 20문제 모드
        left_card = tk.Frame(btn_frame, bg=PANEL_BG, padx=24, pady=20)
        left_card.pack(side='left', padx=12)
        tk.Label(left_card, text='20문제 모드',
                 font=('Apple SD Gothic Neo', 15, 'bold'),
                 bg=PANEL_BG, fg=DARK).pack()
        tk.Label(left_card, text='제한시간 15분\n한 과목 전체 연습',
                 font=('Apple SD Gothic Neo', 11),
                 bg=PANEL_BG, fg=MID, justify='center').pack(pady=(6, 14))
        FlatBtn(left_card, '시작', bg=ACCENT, fg='white', hover_bg='#2962c4',
                font=('Apple SD Gothic Neo', 13, 'bold'), padx=28, pady=8,
                command=lambda: self._dismiss_overlay('full')).pack()

        # 1문제 모드
        right_card = tk.Frame(btn_frame, bg=PANEL_BG, padx=24, pady=20)
        right_card.pack(side='left', padx=12)
        tk.Label(right_card, text='1문제 연습 모드',
                 font=('Apple SD Gothic Neo', 15, 'bold'),
                 bg=PANEL_BG, fg=DARK).pack()
        tk.Label(right_card, text='제한시간 45초\n한 문제씩 반복 연습',
                 font=('Apple SD Gothic Neo', 11),
                 bg=PANEL_BG, fg=MID, justify='center').pack(pady=(6, 14))
        FlatBtn(right_card, '시작', bg='#2ecc71', fg='white', hover_bg='#27ae60',
                font=('Apple SD Gothic Neo', 13, 'bold'), padx=28, pady=8,
                command=lambda: self._dismiss_overlay('single')).pack()

    def _dismiss_overlay(self, mode):
        self._mode = mode
        self._overlay.destroy()
        self._reset_state()
        self._start_subject()

    # ── 타이머 ───────────────────────────────────────────────

    def _open_modal(self, build_fn):
        """루트 위에 반투명 오버레이 + 중앙 카드를 띄우는 헬퍼.
        build_fn(card, close) 호출로 내용을 채움."""
        overlay = tk.Frame(self.root, bg='#1a2a3a')
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.focus_set()
        card = tk.Frame(overlay, bg=BG, padx=32, pady=24)
        card.place(relx=0.5, rely=0.5, anchor='center')
        def close():
            overlay.destroy()
        build_fn(card, close)
        return overlay

    def _go_to_menu(self):
        if self._mode == 'full' and self.ticking:
            def build(card, close):
                tk.Label(card, text='진행 중인 풀이가 있습니다.',
                         font=('Apple SD Gothic Neo', 15, 'bold'),
                         bg=BG, fg=DARK).pack(pady=(0, 6))
                tk.Label(card, text='메인메뉴로 나가면 기록이 사라집니다.',
                         font=('Apple SD Gothic Neo', 12),
                         bg=BG, fg=MID).pack(pady=(0, 24))
                btn_row = tk.Frame(card, bg=BG)
                btn_row.pack()
                FlatBtn(btn_row, '나가기', bg=DANGER, fg='white', hover_bg='#c0392b',
                        font=('Apple SD Gothic Neo', 12, 'bold'), padx=18, pady=7,
                        command=lambda: [close(), self._force_menu()]).pack(side='left', padx=8)
                FlatBtn(btn_row, '계속 풀기', bg='#e0e0e0', fg=DARK, hover_bg='#c8c8c8',
                        font=('Apple SD Gothic Neo', 12), padx=18, pady=7,
                        command=close).pack(side='left', padx=8)
            self._open_modal(build)
        else:
            self._force_menu()

    def _force_menu(self):
        self.ticking = False
        self._reset_state()
        self._memo_panel.reset()
        self._draw_panel.reset()
        self._calc_ref.reset()
        self._show_start_overlay()

    def _update_ans_cell(self, idx, ans):
        cell, lbl = self._ans_cells[idx]
        cell.config(bg=ACCENT)
        for w in cell.winfo_children():
            w.config(bg=ACCENT, fg='white')
        lbl.config(text=str(ans))

    def _clear_ans_cells(self):
        for cell, lbl in self._ans_cells:
            cell.config(bg='#e0e0e0')
            for w in cell.winfo_children():
                w.config(bg='#e0e0e0')
            lbl.config(text='-', fg='#aaaaaa')

    def _reset_state(self):
        self.current_q = 0
        self._selected = 0
        self.answers   = [None] * TOTAL_QUESTIONS
        self.times     = [0.0]  * TOTAL_QUESTIONS
        self._clear_ans_cells()

    def _start_subject(self):
        self.subj_start    = time.time()
        self._alarm_played = False
        self._begin_q()

    def _begin_q(self):
        self.q_start   = time.time()
        self.ticking   = True
        self._selected = 0
        self._reset_ans()
        self.next_btn.set_disabled(False)
        self.next_btn.set_colors(ACCENT, 'white')
        if self._mode == 'single':
            self.q_lbl.config(text='1문제 연습')
            self.total_lbl.config(text='제한시간  00:45', fg=MID)
            self.ans_grid_frame.pack_forget()
            self.next_btn.config(text='다음 문제  →')
        else:
            self.q_lbl.config(text=f'문제 {self.current_q + 1} / {TOTAL_QUESTIONS}')
            self.ans_grid_frame.pack(fill='x', padx=14, pady=(14, 0))
            self.next_btn.config(text='다음 문제  →')
        self.menu_btn.pack(fill='x', padx=14, pady=(8, 0))
        self._tick()

    def _tick(self):
        if not self.ticking:
            return
        now    = time.time()
        q_el   = now - self.q_start
        remain = max(0.0, TIME_LIMIT - (now - self.subj_start))

        qm, qs = divmod(int(q_el), 60)
        qcs = int(q_el * 10) % 10
        self.timer_lbl.config(text=f'{qm:02d}:{qs:02d}.{qcs}',
                              fg=DANGER if q_el > WARN_SECONDS else DARK)
        if self._mode == 'full':
            rm, rs = divmod(int(remain), 60)
            self.total_lbl.config(text=f'남은 시간  {rm:02d}:{rs:02d}',
                                  fg=DANGER if remain < 60 else MID)
            if remain == 0 and not self._alarm_played:
                self._alarm_played = True
                self._play_alarm(3)

        self.root.after(100, self._tick)


    def _play_alarm(self, count):
        if count <= 0:
            return
        subprocess.Popen(['afplay', '/System/Library/Sounds/Glass.aiff'])
        self.root.after(700, lambda: self._play_alarm(count - 1))

    # ── 답 선택 & 이동 ───────────────────────────────────────

    def _select(self, ans):
        # single 모드: 타이머 종료 후에도 답 변경 가능
        if not self.ticking and self._mode != 'single':
            return
        self._deactivate_calc()
        self._selected = ans
        self._reset_ans()
        self.ans_btns[ans - 1].set_colors(ACCENT, 'white')
        self.next_btn.set_disabled(False)
        self.next_btn.set_colors(ACCENT, 'white')

        if self._mode == 'single' and self.ticking:
            # 답 선택 순간 타이머 정지 & 경과시간 저장
            self.times[self.current_q] = time.time() - self.q_start
            self.ticking = False

    def _reset_ans(self):
        for b in self.ans_btns:
            b.set_colors(BTN_BG, DARK)

    def _in_text_widget(self):
        return isinstance(self.root.focus_get(), tk.Text)

    def _route_key_to_calc(self, event):
        """Text 위젯 인터셉터에서 직접 호출 — 이벤트를 계산기 press()로 번역"""
        char = event.keysym
        key_map = {
            'Return': '=', 'KP_Enter': '=',
            'BackSpace': 'BS',
            'c': 'C', 'C': 'C',
            'plus': '+', 'KP_Add': '+',
            'minus': '−', 'KP_Subtract': '−',
            'asterisk': '×', 'KP_Multiply': '×',
            'slash': '÷', 'KP_Divide': '÷',
            'equal': '=', 'KP_Equal': '=',
            'period': '.', 'KP_Decimal': '.',
        }
        for i in range(10):
            key_map[str(i)]        = str(i)
            key_map[f'KP_{i}']     = str(i)
        if char in key_map:
            self._calc_ref.press(key_map[char])

    def _kb_digit(self, event, ch):
        """숫자 키: 계산기 활성이면 무조건 계산기, 아니면 메모장 제외 후 답 선택"""
        if self._calc_active:
            self._calc_ref.press(ch)
            return
        if self._in_text_widget():
            return
        if ch in '12345':
            self._select(int(ch))

    def _kb_calc(self, event, key):
        """계산기 전용 키: 계산기 활성이면 무조건 계산기"""
        if self._calc_active:
            self._calc_ref.press(key)
            return
        # 계산기 비활성 시 메모장 포커스면 위젯이 자체 처리

    def _advance(self):
        if self._mode == 'full' and not self.ticking:
            return

        if self._mode == 'single':
            # 타이머는 _select()에서 이미 정지됨, 경과시간도 저장됨
            self.answers[self.current_q] = self._selected
            self._reset_state()
            self._start_subject()
            return

        # full 모드
        elapsed = time.time() - self.q_start
        self.answers[self.current_q] = self._selected
        self.times[self.current_q]   = elapsed
        self.ticking = False
        self._update_ans_cell(self.current_q, self._selected)
        self.current_q += 1
        if self.current_q >= TOTAL_QUESTIONS:
            self._show_results()
        else:
            self.ticking = True
            self._begin_q()

    # ── 결과 표 ──────────────────────────────────────────────

    def _show_results(self):
        total = sum(self.times)
        tm, ts = divmod(int(total), 60)
        slow   = sum(1 for t in self.times if t > WARN_SECONDS)
        times  = list(self.times)
        answers = list(self.answers)

        def build(card, close):
            tk.Label(card, text='풀이 결과',
                     font=('Apple SD Gothic Neo', 20, 'bold'),
                     bg=BG, fg=DARK).pack(pady=(0, 4))
            tk.Label(card,
                     text=f'총 소요시간: {tm:02d}:{ts:02d}   |   45초 초과: {slow}문제',
                     font=('Apple SD Gothic Neo', 12),
                     bg=BG, fg=MID).pack(pady=(0, 10))

            frame = tk.Frame(card, bg=BG)
            frame.pack(fill='both', expand=True)

            style = ttk.Style(self.root)
            style.theme_use('default')
            style.configure('R.Treeview',
                            background=PANEL_BG, fieldbackground=PANEL_BG,
                            foreground=DARK,
                            font=('Apple SD Gothic Neo', 12), rowheight=28)
            style.configure('R.Treeview.Heading',
                            background='#e0e0e0', foreground=DARK,
                            font=('Apple SD Gothic Neo', 12, 'bold'), relief='flat')
            style.map('R.Treeview',
                      background=[('selected', ACCENT)],
                      foreground=[('selected', 'white')])

            cols = ('no', 'answer', 'elapsed')
            tree = ttk.Treeview(frame, columns=cols, show='headings',
                                height=18, style='R.Treeview')
            tree.heading('no',      text='문제')
            tree.heading('answer',  text='선택한 답')
            tree.heading('elapsed', text='소요 시간')
            tree.column('no',      width=80,  anchor='center')
            tree.column('answer',  width=130, anchor='center')
            tree.column('elapsed', width=170, anchor='center')
            tree.tag_configure('slow', foreground=DANGER)

            for i in range(TOTAL_QUESTIONS):
                t = times[i]
                m, s = divmod(int(t), 60)
                ds   = int((t - int(t)) * 10)
                ans  = str(answers[i]) if answers[i] else 'x'
                tree.insert('', 'end',
                            values=(f'{i+1}번', ans, f'{m:02d}:{s:02d}.{ds}'),
                            tags=('slow',) if t > WARN_SECONDS else ())

            sb = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            tree.pack(side='left', fill='both', expand=True)
            sb.pack(side='right', fill='y')

            FlatBtn(card, '다시 시작',
                    bg=ACCENT, fg='white', hover_bg='#2962c4',
                    font=('Apple SD Gothic Neo', 13),
                    padx=24, pady=8,
                    command=lambda: [close(), self._restart()]).pack(pady=(12, 0))

        self._open_modal(build)

    def _restart(self):
        self.ticking = False
        self._reset_state()
        self._show_start_overlay()


if __name__ == '__main__':
    SKCTApp()
