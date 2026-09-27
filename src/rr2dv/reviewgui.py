"""Pre-build decisions on the Tk thread; cancelling releases the conversion worker."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from . import review


def show(parent, req, answer):
    win = tk.Toplevel(parent)
    win.title('Review ' + req['name'])
    win.geometry('880x720')
    win.transient(parent)
    win.grab_set()
    body = ttk.Frame(win, padding=12)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text=req['name'] + ' — pre-build review', font=('', 14, 'bold')).pack(anchor='w')
    ttk.Label(body, text='Choices are saved with this vehicle and source fingerprint. Physics is experimental; in-game checks are pending.', wraplength=820).pack(anchor='w', pady=5)
    tabs = ttk.Notebook(body)
    tabs.pack(fill='both', expand=True)
    setup, tracks, source = [ttk.Frame(tabs, padding=10) for _ in range(3)]
    for page, title in ((setup, 'Brakes and physics'), (tracks, 'Spawn tracks'), (source, 'Source evidence')):
        tabs.add(page, text=title)
    fields = {}
    choices = [('trainBrake', 'Train brake valve', review.BRAKES, req.get('suggestedBrake') or ''),
               ('spawnMode', 'Spawning', review.SPAWNING, 'radio-only'),
               ('physics', 'Steam profile', review.PHYSICS, 'legacy-equivalent'),
               ('steamHeat', 'Steam thermal regime', review.HEAT, 'basis-approximation'),
               ('cylinders', 'Physical cylinders', ('2', '3', '4'), '2')]
    for row, (key, label, opts, default) in enumerate(choices):
        ttk.Label(setup, text=label).grid(row=row, column=0, sticky='w', pady=4)
        fields[key] = tk.StringVar(value=default)
        ttk.Combobox(setup, textvariable=fields[key], values=opts, state='readonly', width=30).grid(row=row, column=1, sticky='w')
    for row, (key, label) in enumerate((('wheelRadius', 'Driving tyre radius (m)'),
            ('gearRatio', 'Gear reduction: engine RPM / wheel RPM'), ('efficiency', 'Transmission efficiency (0–1)'),
            ('gearEvidence', 'Gear ratio evidence or explicit assumption'), ('poweredWheelsets', 'Geared: physical powered indices, comma separated'), ('unpoweredWheelsets', 'Geared: physical unpowered indices, if any')), start=5):
        ttk.Label(setup, text=label).grid(row=row, column=0, sticky='w', pady=4)
        fields[key] = tk.StringVar(value='1' if key == 'efficiency' else (str(req.get('initialRadius') or '') if key == 'wheelRadius' else ''))
        ttk.Entry(setup, textvariable=fields[key], width=40).grid(row=row, column=1, sticky='w')
    ttk.Label(setup, text='Check Source evidence for measured tyres and wheelset indices.\nGeared: all other indices are shafts/placeholders, with no physical axles.\nIndependent and handbrakes remain separate.\nCompound switching, oil regime combinations and diesel adapters are pending.', wraplength=790).grid(row=12, column=0, columnspan=2, sticky='w', pady=12)
    ttk.Label(tracks, text=f"Required length: {req['requiredTrackLengthM']} m including coupling and clearance.\nAutomatic uses every suitable track. Radio only uses none. Select tracks here for manual mode.", wraplength=790).pack(anchor='w')
    listing = tk.Listbox(tracks, selectmode='multiple', exportselection=False, height=20)
    listing.pack(fill='both', expand=True)
    eligible = [t for t in req['tracks'] if t['suitable']]
    for t in eligible: listing.insert('end', f"{t['name']} — {t['length_m']} m (ID {t['id']})")
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
        v['cylinders'] = int(v['cylinders'])
        v['poweredWheelsets'] = [int(x.strip()) for x in v['poweredWheelsets'].split(',') if x.strip()]
        v['unpoweredWheelsets'] = [int(x.strip()) for x in v['unpoweredWheelsets'].split(',') if x.strip()]
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
            listing.selection_clear(0,'end')
            for i,t in enumerate(eligible):
                if t['id'] in saved['values']['spawnTracks']: listing.selection_set(i)
            ack.set(False)
        except (OSError, ValueError) as e: messagebox.showerror('Cannot reuse review', str(e), parent=win)
    buttons = ttk.Frame(body)
    buttons.pack(fill='x')
    ttk.Button(buttons, text='Load saved review', command=load).pack(side='left')
    ttk.Button(buttons, text='Cancel conversion', command=close).pack(side='right')
    ttk.Button(buttons, text='Save choices and build', command=accept).pack(side='right', padx=8)
    win.protocol('WM_DELETE_WINDOW', close)
