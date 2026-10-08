import psutil
import json
import os
import re
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext


PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".cpu_affinity_profiles")


# ------------------------- Helpers -------------------------

def is_admin():
    """Cross-platform administrator check."""
    try:
        if os.name == 'nt':
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:
        return False


def set_affinity(pid, core_ids):
    """Set CPU affinity. Returns (success, message)."""
    if not isinstance(pid, int) or pid <= 0:
        return False, f"Invalid PID: {pid}"
    if not isinstance(core_ids, (list, tuple)) or not core_ids:
        return False, "Core list must not be empty"
    if not all(isinstance(c, int) and c >= 0 for c in core_ids):
        return False, "Core IDs must be non-negative integers"
    try:
        psutil.Process(pid).cpu_affinity(list(core_ids))
        return True, f"PID {pid} affinity set to cores {sorted(core_ids)}"
    except psutil.NoSuchProcess:
        return False, f"Process {pid} no longer exists"
    except psutil.AccessDenied:
        return False, f"Access denied for PID {pid}. Run as administrator."
    except Exception as e:
        return False, f"Failed for PID {pid}: {e}"


def get_affinity(pid):
    """Read current affinity. Returns (success, list_of_cores_or_msg)."""
    try:
        return True, list(psutil.Process(pid).cpu_affinity())
    except psutil.NoSuchProcess:
        return False, f"Process {pid} not found"
    except psutil.AccessDenied:
        return False, f"Access denied for PID {pid}"
    except Exception as e:
        return False, f"Error reading affinity for PID {pid}: {e}"


def _sanitize_name(name):
    return re.sub(r'[^A-Za-z0-9_\- ]', '', name or '').strip()


def save_profile(profile_name, pid_affinities):
    """Save profile to JSON. Returns (success, message_or_path)."""
    name = _sanitize_name(profile_name)
    if not name:
        return False, "Invalid profile name (letters, digits, spaces, - and _ only)"
    if not isinstance(pid_affinities, dict):
        return False, "Affinity data must be a dictionary"
    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        path = os.path.join(PROFILE_DIR, f"{name}.json")
        serializable = {str(k): sorted(int(c) for c in v) for k, v in pid_affinities.items()}
        with open(path, "w") as f:
            json.dump(serializable, f, indent=4)
        return True, path
    except Exception as e:
        return False, f"Failed to save profile: {e}"


def load_profile(profile_name):
    """Load profile. Returns (success, message_or_path, data_dict)."""
    name = _sanitize_name(profile_name)
    if not name:
        return False, "Invalid profile name", {}
    path = os.path.join(PROFILE_DIR, f"{name}.json")
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False, "Profile format is invalid (expected JSON object)", {}
        normalized = {}
        for k, v in data.items():
            try:
                pid = int(k)
                cores = sorted(int(c) for c in v)
                if pid > 0 and cores:
                    normalized[str(pid)] = cores
            except (ValueError, TypeError):
                continue
        return True, path, normalized
    except FileNotFoundError:
        return False, f"Profile '{name}' not found in {PROFILE_DIR}", {}
    except json.JSONDecodeError as e:
        return False, f"Corrupted profile file: {e}", {}
    except Exception as e:
        return False, f"Failed to load profile: {e}", {}


# ------------------------- GUI -------------------------

class CPUAffinityToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CPU Affinity Tool")
        self.root.geometry("920x700")
        self.root.minsize(820, 600)

        # Style
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except tk.TclError:
            pass

        # State
        self.pid_affinities = {}
        self.profile_name = tk.StringVar()
        self.selected_pid = tk.IntVar(value=0)
        self.filter_var = tk.StringVar()
        self._all_processes = []  # master list for filtering

        logical = psutil.cpu_count(logical=True) or 1
        self.available_cores = list(range(logical))

        # Frames
        self.cpu_info_frame = ttk.LabelFrame(self.root, text="CPU Information")
        self.process_list_frame = ttk.LabelFrame(self.root, text="Running Processes")
        self.affinity_control_frame = ttk.LabelFrame(self.root, text="Affinity Control")
        self.profile_management_frame = ttk.LabelFrame(self.root, text="Profile Management")
        self.log_frame = ttk.LabelFrame(self.root, text="Log")

        self.cpu_info_frame.grid(row=0, column=0, sticky='ew', padx=8, pady=6)
        self.process_list_frame.grid(row=1, column=0, sticky='nsew', padx=8, pady=6)
        self.affinity_control_frame.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=8, pady=6)
        self.profile_management_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=8, pady=6)
        self.log_frame.grid(row=3, column=0, columnspan=2, sticky='nsew', padx=8, pady=6)

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(3, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # Build sections
        self.create_cpu_info_section()
        self.create_process_list_section()
        self.create_affinity_control_section()
        self.create_profile_management_section()
        self.create_log_section()

        # Initial data
        self.populate_process_list()
        self.get_cpu_topology()

        if not is_admin():
            self.log_message(
                "Warning: Not running as administrator. Setting affinity for some processes may fail.",
                'warning'
            )

    # ---------- UI construction ----------

    def create_cpu_info_section(self):
        self.cpu_topology_text = tk.StringVar(value="Loading...")
        ttk.Label(self.cpu_info_frame, textvariable=self.cpu_topology_text,
                  justify='left', anchor='w').pack(fill='x', padx=10, pady=6)

    def create_process_list_section(self):
        toolbar = ttk.Frame(self.process_list_frame)
        toolbar.pack(fill='x', padx=6, pady=(6, 0))

        ttk.Label(toolbar, text="Filter:").pack(side='left')
        ttk.Entry(toolbar, textvariable=self.filter_var, width=24).pack(side='left', padx=6)
        self.filter_var.trace_add('write', lambda *_: self.apply_filter())
        ttk.Button(toolbar, text="Refresh", command=self.populate_process_list).pack(side='right')

        tree_container = ttk.Frame(self.process_list_frame)
        tree_container.pack(fill='both', expand=True, padx=6, pady=6)

        self.process_list = ttk.Treeview(
            tree_container, columns=('PID', 'Name'),
            show='headings', selectmode='browse'
        )
        self.process_list.heading('PID', text='PID')
        self.process_list.heading('Name', text='Name')
        self.process_list.column('PID', width=80, anchor='center', stretch=False)
        self.process_list.column('Name', width=300, anchor='w')

        vsb = ttk.Scrollbar(tree_container, orient='vertical', command=self.process_list.yview)
        self.process_list.configure(yscrollcommand=vsb.set)
        self.process_list.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.process_list.bind('<<TreeviewSelect>>', self.on_process_select)

    def create_affinity_control_section(self):
        pid_frame = ttk.Frame(self.affinity_control_frame)
        pid_frame.pack(fill='x', padx=8, pady=(8, 4))
        ttk.Label(pid_frame, text="Selected PID:").pack(side='left')
        self.selected_pid_label = ttk.Label(pid_frame, text="(none)", foreground='blue')
        self.selected_pid_label.pack(side='left', padx=6)

        check_container = ttk.Frame(self.affinity_control_frame)
        check_container.pack(fill='both', expand=True, padx=8, pady=4)

        self.core_checkboxes = []
        cols = 4 if len(self.available_cores) <= 16 else 6
        for i, core_id in enumerate(self.available_cores):
            var = tk.IntVar(value=0)
            cb = ttk.Checkbutton(check_container, text=f"CPU {core_id}", variable=var)
            cb.grid(row=i // cols, column=i % cols, sticky='w', padx=3, pady=2)
            self.core_checkboxes.append(var)

        btn_row = ttk.Frame(self.affinity_control_frame)
        btn_row.pack(fill='x', padx=8, pady=4)
        ttk.Button(btn_row, text="Select All",
                   command=lambda: self.set_all_cores(1)).pack(side='left', padx=2)
        ttk.Button(btn_row, text="Clear All",
                   command=lambda: self.set_all_cores(0)).pack(side='left', padx=2)

        ttk.Button(self.affinity_control_frame, text="Apply Affinity",
                   command=self.on_set_affinity).pack(pady=(8, 10))

    def create_profile_management_section(self):
        row = ttk.Frame(self.profile_management_frame)
        row.pack(fill='x', padx=8, pady=8)

        ttk.Label(row, text="Profile name:").pack(side='left')
        ttk.Entry(row, textvariable=self.profile_name, width=24).pack(side='left', padx=6)
        ttk.Button(row, text="Save", command=self.on_save_profile).pack(side='left', padx=3)
        ttk.Button(row, text="Load", command=self.on_load_profile).pack(side='left', padx=3)
        ttk.Button(row, text="Open folder",
                   command=self.open_profile_folder).pack(side='left', padx=3)

    def create_log_section(self):
        container = ttk.Frame(self.log_frame)
        container.pack(fill='both', expand=True, padx=6, pady=6)
        self.log_text = scrolledtext.ScrolledText(container, height=6,
                                                  state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)
        self.log_text.tag_config('error',   foreground='red')
        self.log_text.tag_config('info',    foreground='black')
        self.log_text.tag_config('warning', foreground='#B8860B')
        self.log_text.tag_config('success', foreground='#006400')

    # ---------- Thread-safe helpers ----------

    def run_on_ui(self, func, *args, **kwargs):
        """Schedule a callable on the Tk main thread."""
        self.root.after(0, lambda: func(*args, **kwargs))

    def log_message(self, message, tag='info'):
        def _log():
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, message + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        if threading.current_thread() is threading.main_thread():
            _log()
        else:
            self.root.after(0, _log)

    def set_all_cores(self, value):
        for var in self.core_checkboxes:
            var.set(value)

    # ---------- CPU topology ----------

    def get_cpu_topology(self):
        def _work():
            try:
                logical = psutil.cpu_count(logical=True) or 0
                physical = psutil.cpu_count(logical=False) or 0
                lines = [
                    f"Logical cores : {logical}",
                    f"Physical cores: {physical}",
                ]
                if physical and logical > physical:
                    lines.append(f"Hyper-Threading: likely enabled ({logical // physical} threads/core)")
                else:
                    lines.append("Hyper-Threading: disabled or not supported")
                lines.append("Logical CPU IDs: " + " ".join(map(str, self.available_cores)))
                text = "\n".join(lines)
            except Exception as e:
                text = f"Failed to read CPU topology: {e}"
            self.run_on_ui(self.cpu_topology_text.set, text)

        threading.Thread(target=_work, daemon=True).start()

    # ---------- Process list ----------

    def populate_process_list(self):
        def _work():
            try:
                procs = []
                for p in psutil.process_iter(['pid', 'name']):
                    try:
                        info = p.info
                        procs.append((int(info['pid']), info.get('name') or ''))
                    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, TypeError):
                        continue
                procs.sort(key=lambda x: x[0])
            except Exception as e:
                self.log_message(f"Failed to list processes: {e}", 'error')
                return
            self.run_on_ui(self._set_process_data, procs)

        threading.Thread(target=_work, daemon=True).start()

    def _set_process_data(self, procs):
        self._all_processes = procs
        self.apply_filter()

    def apply_filter(self):
        if not hasattr(self, 'process_list'):
            return
        needle = self.filter_var.get().strip().lower()
        self.process_list.delete(*self.process_list.get_children())
        for pid, name in self._all_processes:
            if needle and needle not in name.lower() and needle not in str(pid):
                continue
            self.process_list.insert('', 'end', iid=str(pid), values=(pid, name))

    def on_process_select(self, event=None):
        sel = self.process_list.selection()
        if not sel:
            return
        try:
            pid = int(sel[0])
        except ValueError:
            return
        self.selected_pid.set(pid)
        self.selected_pid_label.config(text=str(pid))
        self.update_core_checkboxes(pid)

    def update_core_checkboxes(self, pid):
        ok, result = get_affinity(pid)
        if not ok:
            self.log_message(f"Could not read affinity for PID {pid}: {result}", 'warning')
            self.set_all_cores(0)
            return
        core_set = set(result)
        for i, core_id in enumerate(self.available_cores):
            self.core_checkboxes[i].set(1 if core_id in core_set else 0)

    # ---------- Actions ----------

    def on_set_affinity(self):
        pid = self.selected_pid.get()
        if pid <= 0:
            messagebox.showerror("Error", "Please select a process from the list first.")
            return
        core_ids = [self.available_cores[i]
                    for i, var in enumerate(self.core_checkboxes) if var.get() == 1]
        if not core_ids:
            messagebox.showerror("Error", "Please select at least one CPU.")
            return

        ok, msg = set_affinity(pid, core_ids)
        if ok:
            self.pid_affinities[str(pid)] = sorted(core_ids)
            self.log_message(msg, 'success')
        else:
            self.log_message(msg, 'error')

    def on_save_profile(self):
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a profile name.")
            return
        if not self.pid_affinities:
            if not messagebox.askyesno("Empty profile",
                                       "No affinity has been applied yet. Save an empty profile?"):
                return
        ok, msg = save_profile(name, self.pid_affinities)
        if ok:
            self.log_message(f"Profile saved: {msg}", 'success')
        else:
            self.log_message(msg, 'error')

    def on_load_profile(self):
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a profile name.")
            return

        ok, msg, data = load_profile(name)
        if not ok:
            self.log_message(msg, 'error')
            return

        self.pid_affinities = dict(data)
        applied = 0
        for pid_str, cores in data.items():
            ok2, msg2 = set_affinity(int(pid_str), cores)
            if ok2:
                applied += 1
            else:
                self.log_message(f"  {msg2}", 'warning')

        self.log_message(
            f"Loaded profile '{name}': {applied}/{len(data)} processes updated.",
            'success'
        )

        if self.selected_pid.get() > 0:
            self.update_core_checkboxes(self.selected_pid.get())

    def open_profile_folder(self):
        try:
            os.makedirs(PROFILE_DIR, exist_ok=True)
            if os.name == 'nt':
                os.startfile(PROFILE_DIR)          # noqa: S606 (intended)
            elif sys.platform == 'darwin':
                os.system(f'open "{PROFILE_DIR}"')
            else:
                os.system(f'xdg-open "{PROFILE_DIR}"')
        except Exception as e:
            self.log_message(f"Could not open profile folder: {e}", 'error')


# ------------------------- Entry point -------------------------

if __name__ == "__main__":
    if not is_admin():
        print("WARNING: Not running as administrator. Some features may be limited.")
    root = tk.Tk()
    app = CPUAffinityToolGUI(root)
    root.mainloop()