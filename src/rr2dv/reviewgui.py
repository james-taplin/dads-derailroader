"""Pre-build decisions on the Tk thread; cancelling releases the conversion worker."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from . import attribution, review


def scroll_with(canvas, frame, item):
    """A frame scrolling inside a canvas at the canvas's width. Each handler changes the other's size, so only real
    changes are applied: unguarded, some Tk builds keep resizing forever with no error (the vehicle choices window
    never appeared and the app hung, Python 3.14 / Tk 9, 2026-09-28)."""
    state = {'region': None, 'width': None}

    def region(_):
        box = canvas.bbox('all')
        if box != state['region']:
            state['region'] = box
            canvas.configure(scrollregion=box)

    def width(event):
        if event.width != state['width']:
            state['width'] = event.width
            canvas.itemconfigure(item, width=event.width)
    frame.bind('<Configure>', region)
    canvas.bind('<Configure>', width)


def show(parent, req, answer):
    win = tk.Toplevel(parent)
    win.title('Review ' + req['name'])
    win.geometry(f'1000x{min(820, max(600, parent.winfo_screenheight() - 100))}')
    win.minsize(900, 600)
    win.transient(parent)
    win.grab_set()
    body = ttk.Frame(win, padding=12)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text=req['name'] + ' — pre-build review', font=('', 14, 'bold')).pack(anchor='w')
    prefill = req.get('prefill', {})
    initial = prefill.get('values', {})
    origin = tk.StringVar(value=prefill.get('origin', 'Review the suggested vehicle settings'))
    ttk.Label(body, textvariable=origin, wraplength=940).pack(anchor='w', pady=5)
    ttk.Label(body, text='Confirm or change the populated choices below. We remember them automatically for this vehicle. No review file is needed.', wraplength=940).pack(anchor='w', pady=5)
    tabs = ttk.Notebook(body)
    tabs.pack(fill='both', expand=True)
    setup_tab, tracks, wheels, source = [ttk.Frame(tabs, padding=10) for _ in range(4)]
    for page, title in ((setup_tab, 'Vehicle choices'), (tracks, 'Spawn tracks'), (wheels, 'Geared wheels'), (source, 'Advanced / source details')):
        tabs.add(page, text=title)
    content = ttk.Frame(tabs, padding=10)
    tabs.add(content, text='Content used')
    ttk.Label(content, text='Credits recorded in the selected source definitions and models.', wraplength=900).pack(anchor='w', pady=(0, 8))
    credits = tk.Text(content, wrap='word', height=12)
    credit_scroll = ttk.Scrollbar(content, orient='vertical', command=credits.yview)
    credit_scroll.pack(side='right', fill='y')
    credits.pack(fill='both', expand=True)
    credits.configure(yscrollcommand=credit_scroll.set)
    credits.insert('1.0', '\n'.join(attribution.source_labels(req.get('sources', []))) or attribution.RIGHTS_NOTICE)
    credits.configure(state='disabled')
    canvas = tk.Canvas(setup_tab, highlightthickness=0)
    scrollbar = ttk.Scrollbar(setup_tab, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    setup = ttk.Frame(canvas)
    form = canvas.create_window((0, 0), window=setup, anchor='nw')
    scroll_with(canvas, setup, form)
    fields = {}
    notes = {}
    def note(key, row):
        text = prefill.get('provenance', {}).get(key, {}).get('evidence', 'Not specified by source; choose here')
        notes[key] = tk.StringVar(value=text)
        label = ttk.Label(setup, textvariable=notes[key], wraplength=360)
        label.grid(row=row, column=2, sticky='w', padx=12, pady=3)
        return label
    choices = [('trainBrake', 'Train brake valve', review.BRAKES, req.get('suggestedBrake') or ''),
               ('spawnMode', 'Spawning', review.SPAWNING, 'radio-only'),
               ('physics', 'Steam profile', review.PHYSICS, 'legacy-equivalent'),
               ('steamHeat', 'Steam thermal regime', review.HEAT, 'basis-approximation'),
               ('cylinders', 'Physical cylinders', ('2', '3', '4'), '2'),
               ('dynamo', 'Dynamo (lamps and cab light)', review.DYNAMO, 'yes')]
    for row, (key, label, opts, default) in enumerate(choices):
        ttk.Label(setup, text=label).grid(row=row, column=0, sticky='w', pady=4)
        fields[key] = tk.StringVar(value=str(initial.get(key, default)))
        ttk.Combobox(setup, textvariable=fields[key], values=opts, state='readonly', width=30).grid(row=row, column=1, sticky='w')
        note(key, row)
    gear_widgets = []
    for row, (key, label) in enumerate((('wheelRadius', 'Driving tyre radius (m)'),
            ('gearRatio', 'Gear reduction: engine RPM / wheel RPM'), ('efficiency', 'Transmission efficiency (0–1)'),
            ('gearEvidence', 'Gear ratio source or assumption')), start=6):
        label_widget = ttk.Label(setup, text=label)
        label_widget.grid(row=row, column=0, sticky='w', pady=4)
        fields[key] = tk.StringVar(value=str(initial.get(key, '1' if key == 'efficiency' else (req.get('initialRadius') or '') if key == 'wheelRadius' else '')))
        entry = ttk.Entry(setup, textvariable=fields[key], width=30)
        entry.grid(row=row, column=1, sticky='w')
        explanation = note(key, row)
        if key != 'wheelRadius': gear_widgets += [label_widget, entry, explanation]
    ttk.Label(setup, text='Firing').grid(row=14, column=0, sticky='w', pady=4)
    fields['firing'] = tk.StringVar(value=str(initial.get('firing', 'hand-fired')))
    ttk.Combobox(setup, textvariable=fields['firing'], values=review.FIRING, state='readonly', width=30).grid(row=14, column=1, sticky='w')
    note('firing', 14)
    candidates = [c for c in req.get('wheelCandidates', []) if c.get('tread')]
    if candidates:
        ttk.Label(setup, text='Measured tyre candidates').grid(row=10, column=0, sticky='w', pady=6)
        candidate_names = [f"{c.get('clip') or 'Wheel group'}: {c['tread']:.6f} m ({c.get('confidence', 'unknown')} confidence)" for c in candidates]
        candidate_box = ttk.Combobox(setup, values=candidate_names, state='readonly', width=40)
        candidate_box.grid(row=10, column=1, columnspan=2, sticky='w')
        def choose_candidate(_):
            candidate = candidates[candidate_box.current()]
            fields['wheelRadius'].set(str(candidate['tread']))
            notes['wheelRadius'].set('Selected measured candidate; confirm it is the driving tyre. ' + '; '.join(candidate.get('notes') or []))
        candidate_box.bind('<<ComboboxSelected>>', choose_candidate)
    ttk.Label(setup, text='Source facts and suggestions are labelled beside each choice. A suggested cylinder count or simulation profile is not a verified physical specification.\nGeared uses a fixed reduction; Gearbox 1/2 do not change gears. Compound switching and calibration remain pending.', wraplength=900).grid(row=11, column=0, columnspan=3, sticky='w', pady=12)
    ttk.Label(wheels, text='Choose the role of each source wheel group. Powered and unpowered mean actual wheels; leave shafts or placeholder groups excluded. Previous choices are restored automatically.', wraplength=900).pack(anchor='w', pady=8)
    wheel_roles = []
    for i, wheel in enumerate(req['wheelsets']):
        row = ttk.Frame(wheels)
        row.pack(fill='x', pady=4)
        name = '/'.join((wheel.get('transform') or {}).get('path') or []) or (wheel.get('animation') or {}).get('clipName') or 'Unnamed group'
        ttk.Label(row, text=f"{name} — {wheel.get('numberOfAxles', '?')} axles, source diameter {wheel.get('diameter', '?')} m", width=68).pack(side='left')
        role = 'Powered' if i in initial.get('poweredWheelsets', []) else 'Unpowered' if i in initial.get('unpoweredWheelsets', []) else 'Excluded'
        variable = tk.StringVar(value=role)
        wheel_roles.append(variable)
        ttk.Combobox(row, textvariable=variable, values=('Powered', 'Unpowered', 'Excluded'), state='readonly', width=15).pack(side='left')
    def update_profile(*_):
        geared = fields['physics'].get() == 'geared'
        for widget in gear_widgets:
            widget.grid() if geared else widget.grid_remove()
        tabs.tab(wheels, state='normal' if geared else 'disabled')
    fields['physics'].trace_add('write', update_profile)
    update_profile()
    from .enginegui import add_tab
    engine = add_tab(tabs, req, fields)
    ttk.Label(tracks, text=f"Required length: {req['requiredTrackLengthM']} m including coupling and clearance.\nAutomatic uses every suitable track. Radio only uses none. Select tracks here for manual mode.", wraplength=790).pack(anchor='w')
    listing = tk.Listbox(tracks, selectmode='multiple', exportselection=False, height=20)
    listing.pack(fill='both', expand=True)
    eligible = [t for t in req['tracks'] if t['suitable']]
    for t in eligible: listing.insert('end', f"{t['name']} — {t['length_m']} m (ID {t['id']})")
    for i, t in enumerate(eligible):
        if t['id'] in initial.get('spawnTracks', []): listing.selection_set(i)
    evidence = tk.Text(source, wrap='word')
    evidence.pack(fill='both', expand=True)
    indexed = [{'index':i, 'source':w} for i,w in enumerate(req['wheelsets'])]
    evidence.insert('end', 'Wheelset indices for the physical-wheel review:\n' + json.dumps(indexed, indent=2) + '\n\n')
    evidence.insert('end', json.dumps({k:req[k] for k in ('sourceSpecs','wheelCandidates','pendingCapabilities','catalogueEvidence')}, indent=2))
    evidence.configure(state='disabled')
    ack = tk.BooleanVar()
    ttk.Checkbutton(body, text='I have reviewed the choices and understand that in-game calibration is pending.', variable=ack).pack(anchor='w', pady=8)
    def close(value=None):
        answer['value'] = value
        answer['event'].set()
        win.destroy()
    def collect():
        v = {k:f.get() for k,f in fields.items()}
        v['engineMetrics'] = engine['collect']()
        v['engineMetricNotes'] = engine['notes'].get()
        v['cylinders'] = int(v['cylinders'])
        v['poweredWheelsets'] = [i for i, role in enumerate(wheel_roles) if role.get() == 'Powered']
        v['unpoweredWheelsets'] = [i for i, role in enumerate(wheel_roles) if role.get() == 'Unpowered']
        v['spawnTracks'] = [eligible[i]['id'] for i in listing.curselection()] if v['spawnMode'] == 'manual' else []
        v['acknowledgeExperimental'] = ack.get()
        return review.resolve(req, {**{k:req[k] for k in ('schema','adapterVersion','vehicleId','fingerprint','catalogueHash')}, 'values':v})
    def accept():
        try: close(collect())
        except (ValueError, TypeError) as e: messagebox.showerror('Review needed', str(e), parent=win)
    def load():
        path = filedialog.askopenfilename(parent=win, filetypes=[('Review JSON','*.json')])
        if not path: return
        try:
            with open(path, encoding='utf-8') as f: saved = review.resolve(req, json.load(f))
            for k, field in fields.items():
                value = saved['values'].get(k, '')
                field.set(','.join(map(str,value)) if isinstance(value,list) else str(value))
                if k in notes: notes[k].set('Imported choice; confirm before building')
            for key, field in engine['fields'].items():
                value = saved['values']['engineMetrics'].get(key)
                field.set('' if value is None else str(value))
            engine['notes'].set(saved['values'].get('engineMetricNotes', ''))
            for i, role in enumerate(wheel_roles):
                role.set('Powered' if i in saved['values'].get('poweredWheelsets', []) else 'Unpowered' if i in saved['values'].get('unpoweredWheelsets', []) else 'Excluded')
            listing.selection_clear(0,'end')
            for i,t in enumerate(eligible):
                if t['id'] in saved['values']['spawnTracks']: listing.selection_set(i)
            ack.set(False)
            origin.set('Imported vehicle choices; these will be remembered when you confirm')
        except (OSError, ValueError) as e: messagebox.showerror('Cannot reuse review', str(e), parent=win)
    buttons = ttk.Frame(body)
    buttons.pack(fill='x')
    ttk.Button(source, text='Import review JSON (optional)', command=load).pack(anchor='w', pady=6)
    ttk.Button(buttons, text='Cancel conversion', command=close).pack(side='right')
    ttk.Button(buttons, text='Save choices and build', command=accept).pack(side='right', padx=8)
    win.protocol('WM_DELETE_WINDOW', close)
    return {'window': win, 'fields': fields, 'wheelRoles': wheel_roles, 'ack': ack, 'collect': collect, 'tabs': tabs, 'wheels': wheels, 'engine': engine}
