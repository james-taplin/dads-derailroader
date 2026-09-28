"""Engine specification form and live, explicitly approximate calculations."""
import tkinter as tk
from tkinter import ttk

from . import enginemetrics


def add_tab(tabs, req, choices):
    page = ttk.Frame(tabs, padding=10)
    tabs.insert(1, page, text='Engine specifications')
    ttk.Label(page, text='Accept the populated values, or enter better figures. Blank optional values retain the current basis. Published TE and driven-wheel weight are comparison data only.', wraplength=900).pack(anchor='w', pady=(0, 8))
    notes_row = ttk.Frame(page)
    notes_row.pack(fill='x', pady=(0, 8))
    ttk.Label(notes_row, text='Source / notes for your edits (optional):').pack(side='left', padx=(0, 8))
    user_notes = tk.StringVar(value=req.get('prefill', {}).get('values', {}).get('engineMetricNotes', ''))
    ttk.Entry(notes_row, textvariable=user_notes).pack(side='left', fill='x', expand=True)
    summary = tk.StringVar()
    ttk.Label(page, textvariable=summary, wraplength=900, justify='left').pack(side='bottom', fill='x', pady=8)
    canvas = tk.Canvas(page, highlightthickness=0)
    scroll = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
    scroll.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    form = ttk.Frame(canvas)
    window = canvas.create_window((0, 0), window=form, anchor='nw')
    form.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfigure(window, width=e.width))
    defaults = req.get('engineMetrics', {})
    initial = req.get('prefill', {}).get('values', {}).get('engineMetrics', defaults.get('values', {}))
    provenance = req.get('prefill', {}).get('metricProvenance', defaults.get('provenance', {}))
    fields, notes = {}, {}

    def collect(): return {key: value.get() for key, value in fields.items()}

    def refresh(*_):
        values = {key: value.get() for key, value in choices.items()}
        values['engineMetrics'] = collect()
        result = enginemetrics.estimates(values, defaults)
        te, adhesion, reference = result['nominalTeLbf'], result['factorOfAdhesion'], result['referenceTeLbf']
        text = [f'Nominal TE estimate: {te:,.0f} lbf ({result["nominalTeKn"]:.1f} kN)' if te else 'Nominal TE: enter bore, stroke, pressure, cylinders and driving radius.']
        text.append(f'Factor of adhesion (driven weight / nominal TE): {adhesion:.2f}' if adhesion else 'Factor of adhesion: requires weight on driven wheels; total locomotive weight is not substituted.')
        if reference:
            text.append(f'Published TE: {reference:,.0f} lbf' + (f' — estimate differs by {result["referenceDifferencePercent"]:+.1f}%' if te else ''))
        if result['legacyTargetLbf']:
            text.append(f'Existing equivalent-bore calibration target: {result["legacyTargetLbf"]:,.0f} lbf (separate from nominal estimate).')
        if result['boilerCylinderVolumeL']:
            text.append(f'Boiler cylindrical volume: {result["boilerCylinderVolumeL"]:,.0f} L' + (f'; with capacity factor: {result["effectiveBoilerVolumeL"]:,.0f} L.' if result['effectiveBoilerVolumeL'] else '; effective capacity factor inherited from the current basis.'))
        text.append('Estimates use 85% of gauge pressure, double-acting simple expansion, physical cylinder count and selected fixed gearing. They are not measured drawbar pull or a compound-engine model.')
        summary.set('\n'.join(text))
        for key, variable in fields.items():
            try: current = float(variable.get()) if variable.get() else None
            except ValueError:
                notes[key].set('Enter a valid number in the displayed units.'); continue
            if current == defaults.get('values', {}).get(key):
                item = defaults.get('provenance', {}).get(key, {})
            elif current == initial.get(key): item = provenance.get(key, {})
            else: item = {'basis': 'edited', 'evidence': 'Your value; recorded when you save choices.'}
            notes[key].set(item.get('basis', 'unknown').replace('_', ' ') + ': ' + item.get('evidence', ''))

    def restore(key):
        value = defaults.get('values', {}).get(key)
        fields[key].set('' if value is None else str(value))

    for row, (key, label, unit, lo, hi, effect) in enumerate(enginemetrics.FIELDS):
        value = initial.get(key)
        fields[key] = tk.StringVar(value='' if value is None else str(value))
        notes[key] = tk.StringVar()
        ttk.Label(form, text=f'{label} ({unit})').grid(row=row*2, column=0, sticky='w', padx=(0, 8), pady=(8, 0))
        ttk.Entry(form, textvariable=fields[key], width=15).grid(row=row*2, column=1, sticky='w')
        ttk.Button(form, text='Restore', command=lambda k=key: restore(k)).grid(row=row*2, column=2, padx=8)
        ttk.Label(form, textvariable=notes[key], wraplength=345).grid(row=row*2, column=3, sticky='w')
        ttk.Label(form, text=effect, wraplength=850).grid(row=row*2+1, column=0, columnspan=4, sticky='w', pady=(0, 5))
    for variable in [*fields.values(), *choices.values()]: variable.trace_add('write', refresh)
    def wheel(event):
        if event.delta: canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'
    for widget in [canvas, form, *form.winfo_children()]: widget.bind('<MouseWheel>', wheel)
    refresh()
    return {'fields': fields, 'collect': collect, 'restore': restore, 'summary': summary, 'page': page, 'notes': user_notes}
