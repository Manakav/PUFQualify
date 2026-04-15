#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PUF Reliability Analyzer (GUI)
- Select multiple .mt0 files
- Mark one as reference
- Enter temperature/voltage metadata per file
- Compute BER and Reliability per-index and overall
- Export per-index CSV

This version bundles fonts at build time and attempts to register bundled
fonts at runtime so the GUI keeps a consistent appearance even on systems
without the font installed.
"""

import os
import sys
import glob
import shutil
import subprocess
import csv
import math
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont

# reuse parsing utilities from analyze_mt0
from analyze_mt0 import (
    parse_mt0,
    build_binary_vectors,
    hamming_distance,
    intra_index_similarity,
    inter_index_similarity,
    format_bit_string,
    overall_inter_similarity,
)


def register_bundled_fonts():
    """If a ./fonts directory is bundled (via PyInstaller --add-data),
    try to register the fonts so Tk can use them.
    - On Windows: call AddFontResourceExW for each .ttf/.otf
    - On other platforms: run fc-cache on the bundled folder (best-effort)
    """
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        fonts_dir = os.path.join(base_path, 'fonts')
        if not os.path.isdir(fonts_dir):
            return
        ttf_files = glob.glob(os.path.join(fonts_dir, '*.ttf')) + glob.glob(os.path.join(fonts_dir, '*.otf'))
        if not ttf_files:
            return
        if sys.platform.startswith('win'):
            try:
                FR_PRIVATE = 0x10
                AddFontResourceExW = ctypes.windll.gdi32.AddFontResourceExW
                for f in ttf_files:
                    try:
                        AddFontResourceExW(f, FR_PRIVATE, 0)
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            try:
                subprocess.run(['fc-cache', '-f', fonts_dir], check=False)
            except Exception:
                pass
    except Exception:
        pass


# Register bundled fonts as early as possible
register_bundled_fonts()


class AnalyzeGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PUF Reliability Analyzer")
        self.geometry("980x640")

        # choose a safe default English font if available
        try:
            available = set(tkfont.families())
            preferred = ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "Tahoma"]
            chosen = None
            for f in preferred:
                if f in available:
                    chosen = f
                    break
            if chosen is None:
                chosen = tkfont.nametofont("TkDefaultFont").actual().get('family', 'TkDefaultFont')
            default_size = 10
            self.option_add("*Font", f"{chosen} {default_size}")
        except Exception:
            pass

        self.file_entries = []  # list of dicts: path,temp,volt,is_ref,vectors,indices,n
        self.last_results = None

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Main reliability tab
        main_tab = ttk.Frame(notebook)
        notebook.add(main_tab, text="Reliability")

        # MT0 analysis tab
        mt0_tab = ttk.Frame(notebook)
        notebook.add(mt0_tab, text="MT0 Analysis")

        # --- Main tab UI (existing layout moved into main_tab) ---
        top = ttk.Frame(main_tab)
        top.pack(fill=tk.BOTH, expand=False, padx=8, pady=8)

        left = ttk.Frame(top)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left, text="Selected MT0 files:").pack(anchor=tk.W)

        self.file_listbox = tk.Listbox(left, height=12)
        self.file_listbox.pack(fill=tk.BOTH, expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_select)

        btns = ttk.Frame(left)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Add files", command=self.add_files).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Remove selected", command=self.remove_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Set as reference", command=self.set_selected_as_ref).pack(side=tk.LEFT, padx=4)

        right = ttk.Frame(top)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(right, text="File path:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.path_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.path_var, width=70).grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(right, text="Temperature (°C):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.temp_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.temp_var, width=20).grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(right, text="Voltage (V):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.volt_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.volt_var, width=20).grid(row=2, column=1, sticky=tk.W, pady=2)

        self.ref_var = tk.BooleanVar()
        ttk.Checkbutton(right, text="Reference file", variable=self.ref_var, command=self._on_ref_check).grid(row=3, column=1, sticky=tk.W, pady=6)

        ttk.Button(right, text="Save metadata", command=self.save_metadata).grid(row=4, column=1, sticky=tk.W)

        # Bottom controls + results (main tab)
        bottom = ttk.Frame(main_tab)
        bottom.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        op_frame = ttk.Frame(bottom)
        op_frame.pack(fill=tk.X)
        ttk.Button(op_frame, text="Compute Reliability", command=self.compute_reliability).pack(side=tk.LEFT, padx=4)
        ttk.Button(op_frame, text="Export CSV (per-index)", command=self.export_csv).pack(side=tk.LEFT, padx=4)

        ttk.Label(bottom, text="Results:").pack(anchor=tk.W)
        self.results_text = tk.Text(bottom, height=20)
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # --- MT0 Analysis tab UI ---
        mt0_top = ttk.Frame(mt0_tab)
        mt0_top.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(mt0_top, text="MT0 file:").grid(row=0, column=0, sticky=tk.W)
        self.mt0_path_var = tk.StringVar()
        ttk.Entry(mt0_top, textvariable=self.mt0_path_var, width=70).grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Button(mt0_top, text="Browse", command=self.browse_mt0_file).grid(row=0, column=2, padx=4)

        ttk.Label(mt0_top, text="Threshold:").grid(row=1, column=0, sticky=tk.W)
        self.mt0_threshold_var = tk.StringVar(value="0.5")
        ttk.Entry(mt0_top, textvariable=self.mt0_threshold_var, width=10).grid(row=1, column=1, sticky=tk.W)

        mt0_btns = ttk.Frame(mt0_tab)
        mt0_btns.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(mt0_btns, text="Run MT0 Analysis", command=self.run_mt0_analysis).pack(side=tk.LEFT, padx=4)
        ttk.Button(mt0_btns, text="Clear", command=lambda: self.mt0_results_text.delete('1.0', tk.END)).pack(side=tk.LEFT, padx=4)

        ttk.Label(mt0_tab, text="MT0 Analysis Output:").pack(anchor=tk.W, padx=8)
        self.mt0_results_text = tk.Text(mt0_tab, height=20)
        self.mt0_results_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Select MT0 files", filetypes=[("MT0 files", "*.mt0"), ("All files", "*.*")])
        if not paths:
            return
        for p in paths:
            if any(e['path'] == p for e in self.file_entries):
                continue
            try:
                df = parse_mt0(p)
                if not df:
                    messagebox.showwarning("Parse failed", f"No valid data parsed: {p}")
                    continue
                vectors = build_binary_vectors(df, threshold=0.5)
                indices = set(vectors.keys())
                n = len(next(iter(vectors.values()))) if vectors else 0
                ent = {'path': p, 'temp': '', 'volt': '', 'is_ref': False, 'vectors': vectors, 'indices': indices, 'n': n}
                self.file_entries.append(ent)
                self.file_listbox.insert(tk.END, os.path.basename(p) + (f"  [n={n}]" if n else ""))
            except Exception as ex:
                messagebox.showerror("Error", f"Error parsing file {p}: {ex}")

    def remove_selected(self):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.file_listbox.delete(idx)
        del self.file_entries[idx]
        self._clear_detail_fields()

    def set_selected_as_ref(self):
        sel = self.file_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Please select a file to be the reference file.")
            return
        idx = sel[0]
        for i, e in enumerate(self.file_entries):
            e['is_ref'] = (i == idx)
        self._refresh_listbox()

    def _on_select(self, event=None):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        ent = self.file_entries[sel[0]]
        self.path_var.set(ent['path'])
        self.temp_var.set(ent.get('temp', ''))
        self.volt_var.set(ent.get('volt', ''))
        self.ref_var.set(ent.get('is_ref', False))

    def _on_ref_check(self):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        val = self.ref_var.get()
        if val:
            for i, e in enumerate(self.file_entries):
                e['is_ref'] = (i == idx)
        else:
            self.file_entries[idx]['is_ref'] = False
        self._refresh_listbox()

    def save_metadata(self):
        sel = self.file_listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Please select a file to save metadata.")
            return
        idx = sel[0]
        ent = self.file_entries[idx]
        ent['temp'] = self.temp_var.get()
        ent['volt'] = self.volt_var.get()
        ent['is_ref'] = self.ref_var.get()
        self._refresh_listbox()
        messagebox.showinfo("Saved", "Metadata saved.")

    def _refresh_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for e in self.file_entries:
            name = os.path.basename(e['path'])
            tags = []
            if e.get('is_ref'):
                tags.append('REF')
            if e.get('temp'):
                tags.append(f"T={e['temp']}")
            if e.get('volt'):
                tags.append(f"V={e['volt']}")
            if e.get('n'):
                tags.append(f"n={e['n']}")
            disp = name + (" [" + ", ".join(tags) + "]" if tags else "")
            self.file_listbox.insert(tk.END, disp)

    def _clear_detail_fields(self):
        self.path_var.set('')
        self.temp_var.set('')
        self.volt_var.set('')
        self.ref_var.set(False)

    def compute_reliability(self):
        if len(self.file_entries) < 2:
            messagebox.showinfo("Info", "Please add at least two MT0 files (one reference + one measurement).")
            return
        refs = [e for e in self.file_entries if e.get('is_ref')]
        if not refs:
            messagebox.showinfo("Info", "Please mark one file as reference (select and check 'Reference file').")
            return
        ref = refs[0]
        others = [e for e in self.file_entries if not e.get('is_ref')]
        m = len(others)

        # common indices
        common_idx = set(ref['indices'])
        for o in others:
            common_idx &= o['indices']
        if not common_idx:
            messagebox.showerror("Error", "Reference file and measurement files have no common indices; cannot compare.")
            return
        n = ref['n']
        if any(o['n'] != n for o in others):
            messagebox.showwarning("Warning", "Some files have different vector lengths (n); results use reference n.")

        per_index = []
        for idx in sorted(common_idx):
            ref_vec = ref['vectors'][idx]
            sum_norm = 0.0
            for o in others:
                hd = hamming_distance(ref_vec, o['vectors'][idx])
                sum_norm += hd / n
            ber_i = (sum_norm / m) * 100.0
            rel_i = 100.0 - ber_i
            per_index.append({'index': idx, 'BER_percent': ber_i, 'Reliability_percent': rel_i})

        overall_rel = sum(r['Reliability_percent'] for r in per_index) / len(per_index)

        measurement_summary = []
        for o in others:
            hd_sum = 0
            for idx in common_idx:
                hd_sum += hamming_distance(ref['vectors'][idx], o['vectors'][idx])
            avg_ber = (hd_sum / (len(common_idx) * n)) * 100.0
            measurement_summary.append({'path': o['path'], 'BER_percent': avg_ber, 'Reliability_percent': 100.0 - avg_ber})

        mean_rel = sum(r['Reliability_percent'] for r in per_index) / len(per_index)
        std_rel = math.sqrt(sum((r['Reliability_percent'] - mean_rel) ** 2 for r in per_index) / len(per_index))
        # compute overall BER mean and std (per-index)
        overall_ber = sum(r['BER_percent'] for r in per_index) / len(per_index)
        std_ber = math.sqrt(sum((r['BER_percent'] - overall_ber) ** 2 for r in per_index) / len(per_index))

        # measurement-file level BER mean/std
        meas_ber_values = [s['BER_percent'] for s in measurement_summary] if measurement_summary else []
        if meas_ber_values:
            meas_ber_mean = sum(meas_ber_values) / len(meas_ber_values)
            meas_ber_std = math.sqrt(sum((x - meas_ber_mean) ** 2 for x in meas_ber_values) / len(meas_ber_values))
        else:
            meas_ber_mean = 0.0
            meas_ber_std = 0.0

        self.results_text.delete('1.0', tk.END)
        self.results_text.insert(tk.END, f"Reference file: {ref['path']}\n")
        self.results_text.insert(tk.END, f"Number of measurement files (m): {m}\n")
        self.results_text.insert(tk.END, f"Common indices count: {len(common_idx)}\n")
        self.results_text.insert(tk.END, f"Vector length n: {n}\n\n")

        self.results_text.insert(tk.END, f"Overall Reliability (mean): {overall_rel:.4f}%\n")
        self.results_text.insert(tk.END, f"Reliability standard deviation (Std): {std_rel:.4f}%\n")
        self.results_text.insert(tk.END, "(Smaller Std indicates more consistent reliability across indices)\n")
        self.results_text.insert(tk.END, f"Overall BER (mean): {overall_ber:.4f}%\n")
        self.results_text.insert(tk.END, f"BER standard deviation (Std): {std_ber:.4f}%\n\n")

        self.results_text.insert(tk.END, "Per-measurement file summary:\n")
        for s in measurement_summary:
            self.results_text.insert(tk.END, f"  {os.path.basename(s['path'])}: BER={s['BER_percent']:.4f}%  Reliability={s['Reliability_percent']:.4f}%\n")

        if meas_ber_values:
            self.results_text.insert(tk.END, f"\nMeasurement-files BER mean: {meas_ber_mean:.4f}%  Std: {meas_ber_std:.4f}%\n")

        self.results_text.insert(tk.END, "\nPer-index results (first 100):\n")
        self.results_text.insert(tk.END, f"{'Index':<10}{'BER(%)':>12}{'Reliability(%)':>18}\n")
        for r in per_index[:100]:
            self.results_text.insert(tk.END, f"{r['index']:<10}{r['BER_percent']:12.4f}{r['Reliability_percent']:18.4f}\n")

        self.results_text.insert(tk.END, "\nTip: Click 'Export CSV' to save full per-index results.\n")

        # 保存完整结果以便导出
        self.last_results = {
            'per_index': per_index,
            'measurement_summary': measurement_summary,
            'ref': ref['path'],
            'm': m,
            'n': n,
            'common_indices_count': len(common_idx),
            'overall_rel': overall_rel,
            'std_rel': std_rel,
            'overall_ber': overall_ber,
            'std_ber': std_ber,
            'meas_ber_mean': meas_ber_mean,
            'meas_ber_std': meas_ber_std,
        }

        # 弹窗显示简短百分比汇总
        try:
            summary = (
                f"Reference: {os.path.basename(ref['path'])}\n"
                f"Measurement files (m): {m}\n"
                f"Common indices: {len(common_idx)}\n"
                f"Vector length n: {n}\n\n"
                f"Overall Reliability (mean): {overall_rel:.4f}%\n"
                f"Reliability Std (Std): {std_rel:.4f}%\n"
                f"Overall BER (mean): {overall_ber:.4f}%\n"
                f"BER Std (Std): {std_ber:.4f}%\n"
                f"Measurement-files BER mean: {meas_ber_mean:.4f}%  Std: {meas_ber_std:.4f}%\n"
            )
            messagebox.showinfo("Summary", summary)
        except Exception:
            pass

    def export_csv(self):
        if not self.last_results:
            messagebox.showinfo("Info", "Please compute reliability first, then export.")
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv'),('All files','*.*')])
        if not path:
            return
        try:
            with open(path, 'w', newline='') as f:
                w = csv.writer(f)
                # Summary section
                w.writerow(['Summary', 'Value'])
                w.writerow(['Reference file', self.last_results.get('ref', '')])
                w.writerow(['Number of measurement files (m)', self.last_results.get('m', '')])
                w.writerow(['Common indices count', self.last_results.get('common_indices_count', '')])
                w.writerow(['Vector length n', self.last_results.get('n', '')])
                w.writerow(['Overall Reliability (mean) (%)', f"{self.last_results.get('overall_rel', 0.0):.6f}"])
                w.writerow(['Reliability Std (%)', f"{self.last_results.get('std_rel', 0.0):.6f}"])
                w.writerow(['Overall BER (mean) (%)', f"{self.last_results.get('overall_ber', 0.0):.6f}"])
                w.writerow(['BER Std (%)', f"{self.last_results.get('std_ber', 0.0):.6f}"])
                w.writerow(['Measurement-files BER mean (%)', f"{self.last_results.get('meas_ber_mean', 0.0):.6f}"])
                w.writerow(['Measurement-files BER Std (%)', f"{self.last_results.get('meas_ber_std', 0.0):.6f}"])
                w.writerow([])

                # Measurement summary
                w.writerow(['Measurement File', 'BER_percent', 'Reliability_percent'])
                for s in self.last_results.get('measurement_summary', []):
                    w.writerow([s['path'], f"{s['BER_percent']:.6f}", f"{s['Reliability_percent']:.6f}"])
                w.writerow([])

                # Per-index details
                w.writerow(['Index', 'BER_percent', 'Reliability_percent'])
                for r in self.last_results.get('per_index', []):
                    w.writerow([r['index'], f"{r['BER_percent']:.6f}", f"{r['Reliability_percent']:.6f}"])
            messagebox.showinfo('Done', f'Exported full results to {path}')
        except Exception as e:
            messagebox.showerror('Export failed', str(e))

    def browse_mt0_file(self):
        p = filedialog.askopenfilename(title="Select MT0 file", filetypes=[("MT0 files", "*.mt0"), ("All files", "*.*")])
        if p:
            self.mt0_path_var.set(p)

    def run_mt0_analysis(self):
        path = self.mt0_path_var.get()
        if not path:
            messagebox.showinfo("Info", "Please choose an MT0 file to analyze.")
            return
        try:
            df = parse_mt0(path)
        except Exception as e:
            messagebox.showerror("Parse failed", f"Error parsing file: {e}")
            return
        if not df:
            messagebox.showinfo("No data", "No valid data parsed from file.")
            return
        try:
            threshold = float(self.mt0_threshold_var.get())
        except Exception:
            threshold = 0.5

        bin_vectors = build_binary_vectors(df, threshold=threshold)
        sorted_indices = sorted(bin_vectors.keys())

        out_lines = []
        out_lines.append(f"File: {path}")
        out_lines.append(f"Loaded samples: {len(sorted_indices)}")
        out_lines.append("=" * 60)
        out_lines.append(f"Per-index 32-bit sequences (threshold={threshold:.3f})")
        out_lines.append("=" * 60)
        for idx in sorted_indices:
            out_lines.append(f"Index {idx:<6}: {format_bit_string(bin_vectors[idx])}")

        out_lines.append("=" * 60)
        out_lines.append("Intra-index analysis (uniformity)")
        out_lines.append("=" * 60)
        intra_results = intra_index_similarity(bin_vectors)
        out_lines.append(f"{'Index':<8} {'1s':<6} {'0s':<6} {'Balance':<10} {'Similarity%'}")
        out_lines.append("-" * 58)
        for idx in sorted(intra_results.keys()):
            r = intra_results[idx]
            eb = r['element_balance']
            out_lines.append(f"{idx:<8} {eb['ones']:<6} {eb['zeros']:<6} {eb['balance_ratio']:.4f}       {r['zero_similarity'] * 100:.2f}%")

        if intra_results:
            similarities = [r['zero_similarity'] for r in intra_results.values()]
            intra_avg_similarity = (sum(similarities) / len(similarities)) * 100
            mean = sum(similarities) / len(similarities)
            stddev = math.sqrt(sum((x - mean) ** 2 for x in similarities) / len(similarities))
            out_lines.append("")
            out_lines.append(f"Overall intra-set average similarity: {intra_avg_similarity:.2f}%")
            out_lines.append(f"Intra-set similarity Std: {stddev * 100:.4f}%")
        else:
            out_lines.append("\nNot enough intra-data to compute similarity.")

        out_lines.append("\n" + "=" * 60)
        out_lines.append("Inter-index analysis (correlation based on Hamming distance)")
        out_lines.append("=" * 60)
        inter_results = inter_index_similarity(bin_vectors)
        distances = [(pair, r['hamming_distance'], r['similarity']) for pair, r in inter_results.items()]
        distances_sorted = sorted(distances, key=lambda x: x[1])

        out_lines.append("\nTop 10 most similar index pairs (lowest Hamming):")
        out_lines.append(f"{'Index Pair':<15} {'Hamming':<10} {'Similarity'}")
        out_lines.append("-" * 40)
        for pair, dist, sim in distances_sorted[:10]:
            out_lines.append(f"{str(pair):<15} {dist:<10} {sim:.4f}")

        out_lines.append("\nTop 10 least similar index pairs (highest Hamming):")
        out_lines.append(f"{'Index Pair':<15} {'Hamming':<10} {'Similarity'}")
        out_lines.append("-" * 40)
        for pair, dist, sim in distances_sorted[-10:]:
            out_lines.append(f"{str(pair):<15} {dist:<10} {sim:.4f}")

        vector_length = len(next(iter(bin_vectors.values()))) if bin_vectors else 0
        if inter_results and vector_length > 0:
            avg_similarity_percent = overall_inter_similarity(inter_results, vector_length)
            inter_similarities = [r['similarity'] for r in inter_results.values()]
            inter_mean = sum(inter_similarities) / len(inter_similarities)
            inter_stddev = math.sqrt(sum((x - inter_mean) ** 2 for x in inter_similarities) / len(inter_similarities))
            out_lines.append("")
            out_lines.append(f"Inter-set average similarity (uniqueness): {avg_similarity_percent:.2f}%")
            out_lines.append(f"Inter-set similarity Std: {inter_stddev * 100:.4f}%")
        else:
            out_lines.append("\nNot enough inter-data to compute similarity.")

        self.mt0_results_text.delete('1.0', tk.END)
        self.mt0_results_text.insert(tk.END, "\n".join(out_lines))


if __name__ == '__main__':
    app = AnalyzeGUI()
    app.mainloop()
